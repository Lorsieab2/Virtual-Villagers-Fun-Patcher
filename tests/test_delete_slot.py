"""Delete Player Slot: every file tied to a save slot to the Recycle Bin (src/vv_delete_slot.py; the Copy Player
Slot window's Delete choice).

The owner (2026-11-23): the slot's save, logs, sidecars, repair copies, family tree files and its files inside
every backup go to the Recycle Bin -- "NOT images".  Every game, from Move Player Slot's test folders
(tests/test_move_slot.py), in a throwaway Documents folder with a fake process list and a FAKE Recycle Bin (a
folder in the temporary directory): the real Recycle Bin is never touched here.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_copy_slot as tc  # noqa: E402
import test_move_slot as tm  # noqa: E402
import vv_copy_slot as cs  # noqa: E402
import vv_copy_slot_window as window  # noqa: E402
import vv_delete_slot as ds  # noqa: E402
import vv_move_slot as ms  # noqa: E402
import vv_repair_copies as rc  # noqa: E402
import vv_save_backup as backup  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402

NOW = tc.NOW
OWN, OLD_DATA, TREES = tc.OWN, tc.OLD_DATA, tc.TREES


class FakeBin:
    """The Recycle Bin, faked: each file moved into a folder of the test's own; ``fail_on`` makes that call
    (counting from 1) fail before moving anything."""

    def __init__(self, place: Path, fail_on: int | None = None):
        self.place = place
        self.place.mkdir(parents=True, exist_ok=True)
        self.calls: list[list[Path]] = []
        self.fail_on = fail_on

    def __call__(self, paths):
        self.calls.append(list(paths))
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            raise OSError("the Recycle Bin refused (test)")
        for path in paths:
            os.rename(path, self.place / f"{sum(len(c) for c in self.calls)}-{len(os.listdir(self.place))}-{path.name}")

    @property
    def sent(self) -> list[Path]:
        return [p for call in self.calls for p in call]


class Base(tm.Base):
    def make(self, tag: str, number: int, suffix: str):
        """Move Player Slot's folder (slot 1: the village and every kind of file, pictures too; slot 2: an
        earlier village's leftovers), a repair copy whose short name lost the slot, a backup of the whole
        folder, and a set-aside folder for each of slots 1 and 2."""
        game, folder, old = super().make(tag, number, suffix)
        shared = f"{OLD_DATA}\\Copies Made Before Repairs"
        titles = f"{OLD_DATA}\\Custom Titles\\Custom Titles - Save 1.dat"
        self.put(folder, f"{shared}\\A very long sidecar name that is cut sh.dat.bak1", b"long copy")
        self.put(folder, f"{shared}\\Graves - Save 2.dat.bak1", b"slot two's")
        self.put(folder, f"{shared}\\{rc.INDEX}", (
            f"# head\r\nA very long sidecar name that is cut sh.dat.bak1\t{titles}\tbefore-z\t2026-11-20 10:00:00\r\n"
            f"Graves - Save 2.dat.bak1\t{OLD_DATA}\\Graves\\Virtual Villagers {number} Graves - Save 2.dat"
            f"\tbefore-y\t2026-11-20 10:00:00\r\n").encode())
        self.put(folder, f"{TREES}\\Virtual Villagers {number} Family Tree - Save 1.png", b"a tree picture")
        backup.copy_save_folder(folder, NOW, suffix="(before copy)")
        for slot in (1, 2):
            aside = cs.set_aside_folder(folder, NOW, slot, f"Earlier {slot}")
            (aside / OWN / f"Save {slot}" / "Data").mkdir(parents=True)
            (aside / OWN / f"Save {slot}" / "Data" / f"x - Save {slot}.dat").write_bytes(b"set aside")
        return game, folder, old

    def everything(self, folder: Path) -> dict[str, bytes]:
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


class DeleteTests(Base):
    def test_every_game_sends_every_file_of_the_slot_to_the_recycle_bin(self) -> None:
        for tag, number, suffix in tc.CASES:
            with self.subTest(game=number, build=tag):
                game, folder, old = self.make(tag, number, suffix)
                (snapshot,) = [p for p in (folder / "Backups").iterdir() if p.is_dir() and not p.name.endswith(("S1", "S2"))]
                before = self.everything(folder)
                live = ms.slot_everything(game, folder, 1)
                inside = ms.slot_everything(game, snapshot, 1)
                pictures = [p for p in live + inside if ds.is_picture(p)]
                self.assertTrue(pictures)
                bin_ = FakeBin(Path(self._tmp.name) / f"bin{number}{tag}")
                result = ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
                self.assertIsNone(result.problem)
                after = self.everything(folder)
                sent = {str(p).casefold() for p in bin_.sent}
                self.assertEqual(sent, {str(p).casefold() for p in result.recycled})
                # The slot is empty: only its pictures are left, here and in the backup.
                self.assertEqual(sorted(map(str, ms.slot_everything(game, folder, 1) + ms.slot_everything(game, snapshot, 1))),
                                 sorted(map(str, pictures)))
                for path in live + inside:
                    self.assertEqual(str(path).casefold() in sent, not ds.is_picture(path), path)
                self.assertFalse(game.save_path(folder, 1).exists())
                self.assertFalse(game.save_path(snapshot, 1).exists())
                # The repair copy whose name lost the slot went too; its index line with it, slot 2's kept.
                shared = folder / OLD_DATA / "Copies Made Before Repairs"
                self.assertFalse((shared / "A very long sidecar name that is cut sh.dat.bak1").exists())
                self.assertEqual([e.copy.name for e in rc.entries(shared)], ["Graves - Save 2.dat.bak1"])
                # Slot 1's set-aside folder and its Backups index line are gone; slot 2's stay.
                index = backup.backups_index(folder / "Backups")
                self.assertNotIn("2026-10-31 1200 s1", index)
                self.assertFalse((folder / "Backups" / "2026-10-31 1200 S1").exists())
                self.assertIn("2026-10-31 1200 s2", index)
                self.assertTrue((folder / "Backups" / "2026-10-31 1200 S2" / OWN / "Save 2" / "Data" / "x - Save 2.dat").is_file())
                deleted = [v for v in index.values() if v[0] == ds.KIND_DELETED]
                self.assertEqual(len(deleted), 1)
                self.assertIn(f"Save 1 - {old} - {len(result.recycled)} file(s) sent to the Recycle Bin", deleted[0][3])
                # The slot list: Save 1 is the empty slot; the other slots as they were.
                new = game.index_path(folder).read_bytes()
                old_index = before[game.index_path(folder).name]
                self.assertEqual(rename.index_name(game, new, 1), rename.EMPTY_SLOT)
                self.assertEqual(new[cs.FLAG_OFFSET[number]], 0)
                for slot in (2, 3, 4, 5):
                    at = game.index_offset(slot)
                    self.assertEqual(new[at:at + game.index_stride], old_index[at:at + game.index_stride])
                # Every other file -- every other slot's, here and in the backup -- is exactly as it was.
                gone = {Path(p).relative_to(folder).as_posix() for p in result.recycled}
                changed = {game.index_path(folder).name, "Backups/Backups Index.txt",
                           f"{OLD_DATA}/Copies Made Before Repairs/{rc.INDEX}",
                           f"Backups/{snapshot.name}/{OLD_DATA}/Copies Made Before Repairs/{rc.INDEX}"}
                self.assertEqual([e.copy.name for e in rc.entries(snapshot / OLD_DATA / "Copies Made Before Repairs")],
                                 ["Graves - Save 2.dat.bak1"])
                for name, data in before.items():
                    if name in gone:
                        self.assertNotIn(name, after)
                    elif name not in changed:
                        self.assertEqual(after.get(name), data, name)
                # The backup is still offered, with slot 1 empty.
                (info,) = backup.list_backups(folder)
                self.assertNotIn(1, {s for s, v in info.villages.items() if v})
                self.assertFalse((folder / OWN / "Save 1" / "Data").exists())

    def test_a_running_game_or_a_changed_slot_is_refused(self) -> None:
        game, folder, _old = self.make("huttest", 5, "Modded 256")
        before = self.everything(folder)
        bin_ = FakeBin(Path(self._tmp.name) / "bin")
        with self.assertRaisesRegex(ds.GameRunning, "Delete Player Slot never"):
            ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses([4242]), now=NOW, recycle=bin_)
        source = cs.read_slots(game, folder).sources[0]
        with self.assertRaises(ds.GameRunning):
            window.confirm_and_delete(lambda *a: True, lambda *a: True, lambda work: work(), game, folder, source,
                                      processes=tc.FakeProcesses([4242]), now=NOW, recycle=bin_)
        shown = ds.plan_delete(game, folder, 1).signature()
        graves = folder / OWN / "Save 1" / "Data" / "Graves" / "Virtual Villagers 5 Graves - Save 1.dat"
        graves.write_bytes(graves.read_bytes() + b"!")
        before[graves.relative_to(folder).as_posix()] = graves.read_bytes()
        with self.assertRaisesRegex(ds.DeleteError, "changed after you confirmed"):
            ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses(), now=NOW, expected=shown, recycle=bin_)
        self.assertEqual(bin_.calls, [])
        self.assertEqual(self.everything(folder), before)

    def test_a_refused_batch_stops_and_says_what_went(self) -> None:
        game, folder, _old = self.make("huttest", 3, "Modded")
        index_before = game.index_path(folder).read_bytes()
        # The first call (the save folder's own files) refused: nothing went, the slot list is as it was.
        bin_ = FakeBin(Path(self._tmp.name) / "bin1", fail_on=1)
        result = ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
        self.assertIn("could not send every file", result.problem)
        self.assertEqual(result.recycled, [])
        self.assertTrue(game.save_path(folder, 1).is_file())
        self.assertEqual(game.index_path(folder).read_bytes(), index_before)
        self.assertTrue(all(p.exists() for p in result.not_recycled))
        # The second call (the backup's) refused: the slot's own files went, the slot list says empty, the
        # backup's files of the slot are still there and listed.
        bin_ = FakeBin(Path(self._tmp.name) / "bin2", fail_on=2)
        result = ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
        self.assertIn("Backups", result.problem)
        self.assertFalse(game.save_path(folder, 1).exists())
        self.assertEqual(rename.index_name(game, game.index_path(folder).read_bytes(), 1), rename.EMPTY_SLOT)
        self.assertTrue(result.not_recycled)
        self.assertTrue(all(p.exists() and "Backups" in p.parts for p in result.not_recycled))
        self.assertTrue(all(not p.exists() for p in result.recycled))


class LongPathPictureTests(Base):
    """Codex review on #847: a backup keeps a long file under a short name in its Long Paths folder, and that
    name can lose the extension: a picture there is told by its own place, and stays."""

    def test_a_long_picture_in_a_backup_stays_and_a_long_sidecar_goes(self) -> None:
        for tag, number, suffix in tc.CASES[:5]:
            with self.subTest(game=number):
                game, folder, _old = self.make(tag, number, suffix)
                (snapshot,) = [p for p in (folder / "Backups").iterdir()
                               if p.is_dir() and not p.name.endswith(("S1", "S2"))]
                long = snapshot / backup.LONG_PATHS
                long.mkdir(exist_ok=True)                 # a backup may already keep long files
                picture = long / "91 Genealogy - Save 1 - Page 2 of a very lo"
                sidecar = long / "92 Graves - Save 1 kept under a long name s"
                picture.write_bytes(b"a picture")
                sidecar.write_bytes(b"graves")
                index = long / backup.LONG_PATHS_INDEX
                index.write_bytes((index.read_bytes() if index.exists() else b"") + (
                    f"{picture.name}\t{TREES}\\Reports\\Virtual Villagers {number} Genealogy - Save 1 - Page 2 of a "
                    f"very long report.png\r\n"
                    f"{sidecar.name}\t{OWN}\\Save 1\\Data\\Graves\\Virtual Villagers {number} Graves kept under a "
                    f"long name - Save 1.dat\r\n").encode())
                plan = ds.plan_delete(game, folder, 1)
                self.assertIn(f"Kept (pictures):  {picture.relative_to(folder)}", plan.preview())
                bin_ = FakeBin(Path(self._tmp.name) / f"bin{number}")
                result = ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
                self.assertIsNone(result.problem)
                self.assertTrue(picture.is_file())
                self.assertFalse(sidecar.exists())
                self.assertIn(str(sidecar).casefold(), {str(p).casefold() for p in bin_.sent})
                self.assertNotIn(str(picture).casefold(), {str(p).casefold() for p in bin_.sent})

    def test_a_kept_copy_of_a_picture_is_a_picture(self) -> None:
        self.assertTrue(ds.is_picture(Path("Genealogy - Save 1.png.bak1")))
        self.assertTrue(ds.is_picture(Path("x - Save 1.png.before-repair")))
        self.assertFalse(ds.is_picture(Path("Genealogy - Save 1.txt.bak1")))


class OwnershipTests(Base):
    """Codex review on #847: a repair copy with no slot in its name is the slot's by its original; a
    set-aside folder is the slot's by its label's own slot field, never by a village named "A - Save 1 - B"."""

    def test_an_index_only_copy_goes_and_another_slots_stays(self) -> None:
        game, folder, old = self.make("huttest", 1, "Modded")
        shared = folder / OLD_DATA / "Copies Made Before Repairs"
        mine = f"{tc.OLD_LOGS}\\Save 1\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt"
        theirs = f"{tc.OLD_LOGS}\\Save 2\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt"
        (shared / "Deaths Log 1.txt.bak1").write_bytes(b"mine")
        (shared / "Deaths Log 1.txt.bak2").write_bytes(b"theirs")
        with open(shared / rc.INDEX, "ab") as index:
            index.write(f"Deaths Log 1.txt.bak1\t{mine}\tbefore-x\t2026-11-20 10:00:00\r\n"
                        f"Deaths Log 1.txt.bak2\t{theirs}\tbefore-x\t2026-11-20 10:00:00\r\n".encode())
        bin_ = FakeBin(Path(self._tmp.name) / "bin")
        ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
        self.assertFalse((shared / "Deaths Log 1.txt.bak1").exists())
        self.assertEqual((shared / "Deaths Log 1.txt.bak2").read_bytes(), b"theirs")
        self.assertIn("Deaths Log 1.txt.bak2", [e.copy.name for e in rc.entries(shared)])
        self.assertNotIn("Deaths Log 1.txt.bak1", [e.copy.name for e in rc.entries(shared)])

    def test_a_village_named_like_a_slot_never_claims_another_slots_set_aside_folder(self) -> None:
        game, folder, _old = self.make("huttest", 3, "Modded")
        later = NOW.replace(minute=5)
        aside = cs.set_aside_folder(folder, later, 2, "A - Save 1 - B")
        (aside / "x - Save 2.dat").write_bytes(b"slot two's")
        self.assertEqual(cs.set_aside_slot("Replaced by copy 2026-10-31 12-05-00 - Save 2 - A - Save 1 - B"), 2)
        self.assertEqual(cs.set_aside_slot("Replaced by move 2026-10-31 12-05-00 - Save 1 - X"), 1)
        self.assertIsNone(cs.set_aside_slot("Something - Save 1 - else"))
        plan = ds.plan_delete(game, folder, 1)
        self.assertNotIn(aside, [g.aside for g in plan.groups])
        bin_ = FakeBin(Path(self._tmp.name) / "bin")
        ds.delete_slot(game, folder, 1, processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
        self.assertEqual((aside / "x - Save 2.dat").read_bytes(), b"slot two's")


class ConfirmationTests(Base):
    def test_no_at_either_question_changes_nothing(self) -> None:
        for preview_says, final_says in ((False, True), (True, False)):
            with self.subTest(preview=preview_says, final=final_says):
                game, folder, old = self.make("huttest", 2, f"Modded {preview_says}")
                before = self.everything(folder)
                asked, shown = [], []

                def preview(parent, title, message, lines, question):
                    shown.append((title, message, lines, question))
                    return preview_says

                def ask(parent, title, message):
                    asked.append(message)
                    return final_says

                bin_ = FakeBin(Path(self._tmp.name) / f"bin{preview_says}")
                source = cs.read_slots(game, folder).sources[0]
                result = window.confirm_and_delete(ask, preview, lambda work: work(), game, folder, source,
                                                   processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
                self.assertIsNone(result)
                self.assertEqual(bin_.calls, [])
                self.assertEqual(self.everything(folder), before)
                ((title, message, lines, question),) = shown
                self.assertEqual((title, question), ("Delete Player Slot", "Delete it?"))
                self.assertIn("goes to the Recycle Bin", message)
                self.assertIn("Pictures stay where they are", message)
                text = "\n".join(lines)
                self.assertIn(f"Recycled:  {game.save_path(folder, 1).name}", text)
                self.assertIn(f"Kept (pictures):  {TREES}\\Virtual Villagers 2 Family Tree - Save 1.png", text)
                self.assertIn("Recycled:  Backups\\", text)
                if preview_says:
                    self.assertEqual(len(asked), 1)
                    self.assertIn(f"Delete {old} from Save 1?", asked[0])

    def test_yes_to_both_recycles(self) -> None:
        game, folder, _old = self.make("huttest", 4, "Modded")
        bin_ = FakeBin(Path(self._tmp.name) / "bin")
        source = cs.read_slots(game, folder).sources[0]
        result = window.confirm_and_delete(lambda *a: True, lambda *a: True, lambda work: work(), game, folder, source,
                                           processes=tc.FakeProcesses(), now=NOW, recycle=bin_)
        self.assertIsNone(result.problem)
        self.assertFalse(game.save_path(folder, 1).exists())


class GuiWiringTests(unittest.TestCase):
    def test_the_copy_window_offers_delete_through_both_questions(self) -> None:
        source = (ROOT / "src" / "vv_copy_slot_window.py").read_text(encoding="utf-8")
        body = source[source.index("def open_copy_slot("):]
        self.assertIn('value="delete"', body)
        self.assertIn("confirm_and_delete(\n                ask_yes_no, ask_preview,", body)
        self.assertNotIn("vv_delete_slot.delete_slot(", body)
        module = (ROOT / "src" / "vv_delete_slot.py").read_text(encoding="utf-8")
        self.assertIn("vv_translations.recycle(paths)", module)          # the shell's Recycle Bin, never a delete
        self.assertNotIn("unlink(", module)
        self.assertNotIn("rmtree", module)


if __name__ == "__main__":
    unittest.main()
