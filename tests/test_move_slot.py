"""Move Player Slot: a village moved, with everything tied to its slot, into another slot of the same save
folder (src/vv_move_slot.py; the Copy Player Slot window's Move choice, src/vv_copy_slot_window.py).

The owner (2026-11-22): "add a utility to transfer save files AND BACKUPS AND LOGS AND ALL DATA FILES TIED TO
A SAVE SLOT TO A DIFFERENT SLOT".  Every game, from the real test saves of tests/fixtures/rename_tribe (Copy
Player Slot's own test folders, tests/test_copy_slot.py), in a throwaway Documents folder with a fake process
list: nothing here reads or writes outside it, no game is started.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import test_copy_slot as tc  # noqa: E402  (its save folders, fake processes and helpers)
import vv_copy_slot as cs  # noqa: E402
import vv_copy_slot_window as window  # noqa: E402
import vv_move_slot as ms  # noqa: E402
import vv_save_backup as backup  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402

NOW = tc.NOW
OWN, OLD_LOGS, OLD_DATA, TREES = tc.OWN, tc.OLD_LOGS, tc.OLD_DATA, tc.TREES
OLD_TIME = tc.OLD_TIME


class Base(tc.Base):
    def make(self, tag: str, number: int, suffix: str):
        """Copy Player Slot's folder (slot 1: the village and every kind of file; slot 2: only an earlier
        village's leftovers), and more of slot 1's: repair copies, reports, a pending repair, a Reconciliation
        report, a picture, a kept ".before-" copy of a log."""
        game, folder, old = super().make(tag, number, suffix)
        header = f"Village: {old} (Save 1)"
        self.put(folder, f"{OWN}\\Save 1\\Data\\Copies Made Before Repairs\\Data\\Village Masks\\"
                         f"Village Masks - Save 1.dat.before-v1.35.59-repair", b"old masks")
        self.put(folder, f"{OWN}\\Save 1\\Data\\Village Elders\\Village Elders - Save 1.dat",
                 f"VVFP VILLAGE ELDERS v2 game={number}\r\ngraves_seen=0\r\n".encode())
        self.put(folder, f"{OLD_DATA}\\Log Checks\\Virtual Villagers {number} Repair Approved - Save 1.dat",
                 b"VRA1" + struct.pack("<3I", 1, number, 1))
        self.put(folder, f"{OLD_DATA}\\Copies Made Before Repairs\\Custom Titles - Save 1.dat.before-x", b"t")
        self.put(folder, f"{OWN}\\Save 1\\Logs\\Reconciliation\\Virtual Villagers {number} Reconciliation - Save 1.txt",
                 f"Save 1: {old}\r\n{header}\r\nAll agree.\r\n".encode("latin-1"))
        self.put(folder, f"{OWN}\\Save 1\\Logs\\Repairs Made\\Virtual Villagers {number} Repairs Log 1.txt.before-x",
                 f"{header}\r\nRepair 4\r\n".encode("latin-1"))
        self.put(folder, f"{TREES}\\Reports\\Virtual Villagers {number} Genealogy - Save 1 - Page 2.png", b"png")
        self.put(folder, f"{TREES}\\Reports\\Virtual Villagers {number} Genealogy - Save 1.html", b"<html/>")
        self.put(folder, f"{TREES}\\Virtual Villagers {number} Village Matchmaker - Save 1.txt", b"report")
        self.put(folder, "Village Statistics - Save 1.txt", b"old stats")
        return game, folder, old

    def every_file(self, folder: Path) -> dict[str, bytes]:
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*"))
                if p.is_file() and "Backups" not in p.relative_to(folder).parts}


class MoveTests(Base):
    def test_every_game_moves_everything_of_the_slot(self) -> None:
        for tag, number, suffix in tc.CASES:
            with self.subTest(game=number, build=tag):
                game, folder, old = self.make(tag, number, suffix)
                before = self.every_file(folder)
                slot1 = {str(p.relative_to(folder).as_posix()) for p in ms.slot_everything(game, folder, 1)}
                result = ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses(), now=NOW)
                after = self.every_file(folder)
                # Nothing of Save 1 is left; everything else that was there is as it was (but the slot list
                # and the shared words file, a line appended), and Save 1's files are all in Save 3.
                index = game.index_path(folder).name
                shared = f"{OLD_DATA}/Like and Dislike Words/Virtual Villagers {number} Log Words.dat"
                self.assertEqual(ms.slot_everything(game, folder, 1), [])
                for name, data in before.items():
                    if name in slot1:
                        self.assertNotIn(name, after, name)
                    elif name not in (index, shared):
                        self.assertEqual(after[name], data, name)
                self.assertTrue(after[shared].startswith(before[shared]))
                self.assertEqual(len(result.moved), len(slot1))
                self.assertFalse((folder / OWN / "Save 1").exists())
                self.assertFalse((folder / OLD_LOGS / "Save 1").exists())
                # The save and the game's older generations, byte for byte.
                save = before[game.save_path(folder, 1).name]
                self.assertEqual(game.save_path(folder, 3).read_bytes(), save)
                self.assertEqual(backup.read_village_name(number, game.save_path(folder, 3)), old)
                for generation in rename.GENERATIONS:
                    self.assertFalse(game.generation_path(folder, generation, 1).exists())
                    self.assertTrue(game.generation_path(folder, generation, 3).is_file())
                # The slot list: Save 3 holds the village, Save 1 is the slot screen's empty slot.
                new_index = after[index]
                self.assertEqual(rename.index_name(game, new_index, 3), old)
                self.assertEqual(rename.index_name(game, new_index, 1), rename.EMPTY_SLOT)
                self.assertEqual(new_index[cs.FLAG_OFFSET[number] + 2], 1)
                self.assertEqual(new_index[cs.FLAG_OFFSET[number]], 0)
                for slot in (2, 4, 5):
                    at = game.index_offset(slot)
                    self.assertEqual(new_index[at:at + game.index_stride], before[index][at:at + game.index_stride])
                    self.assertEqual(new_index[cs.FLAG_OFFSET[number] + slot - 1],
                                     before[index][cs.FLAG_OFFSET[number] + slot - 1])
                # Logs: the village's lines name Save 3; another village's line is left alone.
                births = (f"{OWN}/Save 3/Logs/Births and Conceptions/"
                          f"Virtual Villagers {number} Births and Conceptions Log 1.txt")
                text = after[births].decode("latin-1")
                self.assertIn(f"Village: {old} (Save 3)", text)
                self.assertNotIn(f"Village: {old} (Save 1)", text)
                self.assertIn("Village: Someone Else (Save 1)", text)
                self.assertIn("Conception 1\r\n", text)                  # never renumbered: the same village
                recon = after[f"{OWN}/Save 3/Logs/Reconciliation/Virtual Villagers {number} Reconciliation - Save 3.txt"]
                self.assertTrue(recon.startswith(f"Save 3: {old}\r\nVillage: {old} (Save 3)".encode("latin-1")))
                kept = after[f"{OWN}/Save 3/Logs/Repairs Made/Virtual Villagers {number} Repairs Log 1.txt.before-x"]
                self.assertEqual(kept, f"Village: {old} (Save 3)\r\nRepair 4\r\n".encode("latin-1"))
                # Binary markers: the slot field (and the village id) are Save 3's.
                paid = after[f"{OWN}/Save 3/Data/Paid Purchases/Virtual Villagers {number} Paid Purchases - Save 3.dat"]
                self.assertEqual(struct.unpack_from("<I", paid, 12)[0], 3)
                arrivals = after[f"{OWN}/Save 3/Data/Arrivals/Virtual Villagers {number} Arrivals Recorded - Save 3.dat"]
                self.assertEqual(struct.unpack_from("<2I", arrivals, 12), (3, tc.fnv(f"Village: {old} (Save 3)")))
                approval = after[f"{OLD_DATA}/Log Checks/Virtual Villagers {number} Repair Approved - Save 3.dat"]
                self.assertEqual(struct.unpack_from("<I", approval, 12)[0], 3)   # a pending repair moves with it
                self.assertEqual(after[f"{OWN}/Save 3/Data/Graves/Virtual Villagers {number} Graves - Save 3.dat"],
                                 before[f"{OWN}/Save 1/Data/Graves/Virtual Villagers {number} Graves - Save 1.dat"])
                self.assertEqual(after[f"{OWN}/Save 3/Data/Village Elders/Village Elders - Save 3.dat"],
                                 before[f"{OWN}/Save 1/Data/Village Elders/Village Elders - Save 1.dat"])
                # Log Decisions: the village's decision filed under Save 3; another village's left as it was.
                decisions = json.loads(after[f"{OWN}/Save 3/Data/Log Checks/Virtual Villagers {number} Log "
                                             f"Decisions - Save 3.json"])["decisions"]
                self.assertEqual([d["village"] for d in decisions],
                                 [f"Village: {old} (Save 3)", "Village: Other (Save 1)"])
                # The save's own words file keys the moved log; the older layout's log got its boundary.
                words = after[f"{OWN}/Save 3/Data/Like and Dislike Words/Virtual Villagers {number} Log Words.dat"]
                self.assertIn(births.replace("/", "\\").encode(), words)
                self.assertNotIn(b"Save 1\\", words)
                deaths_key = f"{OLD_LOGS}\\Save 3\\Deaths and Disappearances\\Virtual Villagers {number} Deaths Log 1.txt"
                self.assertIn(f"0\t{deaths_key}".encode(), after[shared])
                self.assertIn(f"Village: {old} (Save 3)".encode("latin-1"),
                              after[deaths_key.replace("\\", "/")])
                # Repair copies, reports, pictures, trees and the oldest builds' files, renamed for Save 3.
                for name in (f"{OWN}/Save 3/Data/Copies Made Before Repairs/Data/Village Masks/"
                             "Village Masks - Save 3.dat.before-v1.35.59-repair",
                             f"{OLD_DATA}/Copies Made Before Repairs/Custom Titles - Save 3.dat.before-x",
                             f"{OLD_DATA}/Custom Titles/Custom Titles - Save 3.dat",
                             f"{TREES}/Reports/Virtual Villagers {number} Genealogy - Save 3 - Page 2.png",
                             f"{TREES}/Reports/Virtual Villagers {number} Genealogy - Save 3.html",
                             f"{TREES}/Virtual Villagers {number} Village Matchmaker - Save 3.txt",
                             "vvfp_masks_3.dat", "Village Statistics - Save 3.txt"):
                    self.assertIn(name, after, name)
                tree = json.loads(after[f"{TREES}/{old} (Save 3) Family Tree.vvtree"])
                self.assertEqual((tree["slot"], tree["tribe"], tree["game"]), (3, old, number))
                if number == 2:
                    totem = after[f"{OWN}/Save 3/Data/Elder Totems/ElderTotems.dat"]
                    self.assertEqual(struct.unpack_from("<I", totem, 24)[0], 3)
                if number == 3:
                    faction = after[f"{OWN}/Save 3/Data/Factions/Virtual Villagers 3 Second Faction - Save 3.dat"]
                    self.assertEqual(struct.unpack_from("<I", faction, 12)[0], 3)
                # Every moved file keeps its times, the rewritten ones too.
                for _old, new in result.moved:
                    self.assertEqual(os.stat(new).st_mtime_ns, OLD_TIME, new)
                # The backup first, labelled; the Repairs record lists the files.
                (made,) = self.backups(folder)
                self.assertEqual(backup.backups_index(folder / "Backups")[made.casefold()][3], "(before move)")
                record = (folder / OWN / "Save 3" / "Logs" / "Repairs Made" /
                          f"Virtual Villagers {number} Repairs Log 1.txt").read_bytes().decode("latin-1")
                self.assertIn(f"Village: {old} (Save 3)\r\nRepair ", record)
                self.assertIn("  Moved: Virtual Villagers Fun Patcher\\Save 1\\Logs\\Births and Conceptions\\", record)
                self.assertIn("  Backup: Backups\\", record)
                self.assertIsNone(result.set_aside)        # Save 3 had nothing

    def test_the_target_slot_leftovers_are_set_aside(self) -> None:
        """Save 2 has no save but an earlier village's files (its older generation, graves in both layouts):
        they go into Backups -- the owner's first move, New Believers' Save 1 into Save 2, is this."""
        for tag, number, suffix in tc.CASES:
            with self.subTest(game=number, build=tag):
                game, folder, old = self.make(tag, number, suffix)
                self.put(folder, game.generation_path(folder, "2", 2).name, b"an earlier village's generation")
                leftovers = {p.relative_to(folder).as_posix(): p.read_bytes()
                             for p in ms.slot_everything(game, folder, 2)}
                self.assertEqual(len(leftovers), 3)
                save = game.save_path(folder, 1).read_bytes()
                generation = game.generation_path(folder, "2", 1).read_bytes()
                result = ms.move_slot(game, folder, 1, 2, processes=tc.FakeProcesses(), now=NOW)
                self.assertEqual(result.set_aside.name, "2026-10-31 1200 S2")
                for name, data in leftovers.items():
                    self.assertEqual((result.set_aside / name).read_bytes(), data, name)
                self.assertEqual(backup.backups_index(folder / "Backups")["2026-10-31 1200 s2"][3],
                                 "Replaced by move 2026-10-31 12-00-00 - Save 2 - no village")
                self.assertEqual(game.generation_path(folder, "2", 2).read_bytes(), generation)
                self.assertEqual(game.save_path(folder, 2).read_bytes(), save)
                self.assertFalse(game.save_path(folder, 1).exists())

    def test_an_occupied_target_is_replaced_and_kept(self) -> None:
        for tag, number, suffix in tc.CASES[:5]:
            with self.subTest(game=number):
                game, folder, old = self.make(tag, number, suffix)
                files = self.occupy(game, folder, 4, "Old Village")
                result = ms.move_slot(game, folder, 1, 4, processes=tc.FakeProcesses(), now=NOW)
                self.assertEqual(result.overwritten, "Old Village")
                for name, data in files.items():
                    self.assertEqual((result.set_aside / name).read_bytes(), data, name)
                self.assertEqual(rename.save_name(game, game.save_path(folder, 4).read_bytes()), old)
                self.assertEqual(backup.backups_index(folder / "Backups")["2026-10-31 1200 s4"][3],
                                 "Replaced by move 2026-10-31 12-00-00 - Save 4 - Old Village")
                births = (folder / OWN / "Save 4" / "Logs" / "Births and Conceptions" /
                          f"Virtual Villagers {number} Births and Conceptions Log 1.txt").read_bytes()
                self.assertNotIn(b"Old Village", births)

    def test_any_failure_puts_everything_back(self) -> None:
        game, folder, _old = self.make("huttest", 5, "Modded")
        self.occupy(game, folder, 2, "Old Village")
        count = len(ms.plan_move(game, folder, 1, 2).moves)
        for fail in (0, 1, count // 2, count - 1, count):
            with self.subTest(fail=fail):
                before = self.every_file(folder)
                with self.assertRaisesRegex(ms.MoveError, "every file was put back"):
                    if fail == count:
                        # Past every file: the check at the end fails (the slot list read back differently).
                        with unittest.mock.patch.object(ms, "verify", side_effect=ms.MoveError("checked")):
                            ms.move_slot(game, folder, 1, 2, processes=tc.FakeProcesses(), now=NOW)
                    else:
                        ms.move_slot(game, folder, 1, 2, processes=tc.FakeProcesses(), now=NOW, _fail_after=fail)
                after = self.every_file(folder)
                self.assertEqual(after, before)
                for path in folder.rglob("*"):
                    if path.is_file() and "Backups" not in path.relative_to(folder).parts:
                        self.assertEqual(os.stat(path).st_mtime_ns, OLD_TIME, path)
                # The set-aside folder made for the try is gone again; the backup stays.
                self.assertEqual([n for n in self.backups(folder) if n.endswith("S2")], [])

    def test_a_running_game_is_refused_and_nothing_written(self) -> None:
        game, folder, _old = self.make("huttest", 5, "Modded 256")
        before = self.every_file(folder)
        with self.assertRaisesRegex(ms.GameRunning, "Move Player Slot never"):
            ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses([4242]), now=NOW)
        source = cs.read_slots(game, folder).sources[0]
        with self.assertRaises(ms.GameRunning):
            window.confirm_and_move(lambda *a: True, lambda *a: True, lambda work: work(), game, folder, source, 3,
                                    processes=tc.FakeProcesses([4242]), now=NOW)
        self.assertEqual(self.every_file(folder), before)
        self.assertEqual(self.backups(folder), [])

    def test_a_changed_slot_after_confirming_is_refused(self) -> None:
        game, folder, _old = self.make("huttest", 4, "Modded")
        shown = ms.plan_move(game, folder, 1, 3).signature()
        self.put(folder, f"{OWN}\\Save 1\\Data\\Graves\\new - Save 1.dat", b"new")
        with self.assertRaisesRegex(ms.MoveError, "changed after you confirmed"):
            ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses(), now=NOW, expected=shown)
        self.assertEqual(self.backups(folder), [])

    def test_other_slots_and_another_games_files_are_never_touched(self) -> None:
        game, folder, _old = self.make("huttest", 3, "Modded")
        self.put(folder, f"{OLD_DATA}\\Graves\\Virtual Villagers 4 Graves - Save 1.dat", b"another game's")
        self.put(folder, f"{OWN}\\Save 5\\Data\\x - Save 5.dat", b"slot five")
        ms.move_slot(game, folder, 1, 3, processes=tc.FakeProcesses(), now=NOW)
        self.assertEqual((folder / OLD_DATA / "Graves" / "Virtual Villagers 4 Graves - Save 1.dat").read_bytes(),
                         b"another game's")
        self.assertEqual((folder / OWN / "Save 5" / "Data" / "x - Save 5.dat").read_bytes(), b"slot five")


class NameTests(unittest.TestCase):
    def test_every_slot_mark_in_a_name(self) -> None:
        game = rename.GAMES[4]
        cases = {
            "Virtual Villagers - New Believers1.ldw": "Virtual Villagers - New Believers2.ldw",
            "Virtual Villagers - New Believers21.ldw": "Virtual Villagers - New Believers22.ldw",
            "Virtual Villagers - New Believers41.ldw": "Virtual Villagers - New Believers42.ldw",
            "vvfp_masks_1.dat": "vvfp_masks_2.dat",
            "Village Statistics - Save 1.txt": "Village Statistics - Save 2.txt",
            r"Virtual Villagers Fun Patcher\Save 1\Logs\Births and Conceptions\Virtual Villagers 5 Births and "
            r"Conceptions Log 1.txt":
                r"Virtual Villagers Fun Patcher\Save 2\Logs\Births and Conceptions\Virtual Villagers 5 Births and "
                r"Conceptions Log 1.txt",
            r"Virtual Villagers Fun Patcher\Save 1\Data\Copies Made Before Repairs\Data\Village Masks\Village Masks"
            r" - Save 1.dat.before-v1.35.59-repair-2":
                r"Virtual Villagers Fun Patcher\Save 2\Data\Copies Made Before Repairs\Data\Village Masks\Village "
                r"Masks - Save 2.dat.before-v1.35.59-repair-2",
            r"Virtual Villagers Fun Patcher Family Trees\Reports\Virtual Villagers 5 Genealogy - Save 1 - Page 2.png":
                r"Virtual Villagers Fun Patcher Family Trees\Reports\Virtual Villagers 5 Genealogy - Save 2 - Page 2.png",
            r"Virtual Villagers Fun Patcher Family Trees\Kalahuna Tribe 5 (Save 1) Family Tree.vvtree":
                r"Virtual Villagers Fun Patcher Family Trees\Kalahuna Tribe 5 (Save 2) Family Tree.vvtree",
        }
        for old, new in cases.items():
            self.assertEqual(ms.moved_relative(game, Path(old), 1, 2), Path(new))


class ConfirmationTests(Base):
    """A target that holds a player gets its replace question first; then every file is listed.  No (the
    default) writes nothing, not even the backup."""

    def test_no_writes_nothing(self) -> None:
        for target, occupied, refuse_at in ((3, False, 0), (2, True, 0), (2, True, 1)):
            with self.subTest(target=target, occupied=occupied, refuse_at=refuse_at):
                game, folder, old = self.make("huttest", 5, f"Modded {target}{refuse_at}")
                if occupied:
                    self.occupy(game, folder, 2, "Old Village")
                before = self.every_file(folder)
                asked, previewed, ran = [], [], []

                def ask(parent, title, message):
                    asked.append(message)
                    return refuse_at != 0

                def preview(parent, title, message, lines):
                    previewed.append((message, lines))
                    return False

                source = cs.read_slots(game, folder).sources[0]
                result = window.confirm_and_move(ask, preview, lambda work: ran.append(work), game, folder, source,
                                                 target, processes=tc.FakeProcesses(), now=NOW)
                self.assertIsNone(result)
                self.assertEqual(ran, [])
                self.assertEqual(self.every_file(folder), before)
                self.assertEqual(self.backups(folder), [])
                self.assertEqual(len(asked), 1 if occupied else 0)
                if occupied:
                    self.assertIn("Save 2 holds the Old Village village", asked[0])
                self.assertEqual(len(previewed), 0 if occupied and refuse_at == 0 else 1)

    def test_the_preview_lists_every_file_and_yes_moves_exactly_them(self) -> None:
        game, folder, old = self.make("huttest", 5, "Modded 256")
        everything = ms.slot_everything(game, folder, 1)
        leftovers = ms.slot_everything(game, folder, 2)
        shown = []

        def preview(parent, title, message, lines):
            shown.append((title, message, lines))
            return True

        source = cs.read_slots(game, folder).sources[0]
        result = window.confirm_and_move(lambda *a: True, preview, lambda work: work(), game, folder, source, 2,
                                         processes=tc.FakeProcesses(), now=NOW)
        ((title, message, lines),) = shown
        self.assertEqual(title, "Move Player Slot")
        self.assertIn(f"{old} will move from Save 1 to Save 2, keeping its name", message)
        self.assertIn("Leftover files from an earlier village in Save 2 are kept in Backups\\2026-10-31 1200 S2",
                      message)
        text = "\n".join(lines)
        for path in everything:
            self.assertIn(str(path.relative_to(folder)), text)
        for path in leftovers:
            self.assertIn(f"Kept in Backups\\2026-10-31 1200 S2:  {path.relative_to(folder)}", text)
        self.assertEqual(len(result.moved), len(everything))
        self.assertFalse(game.save_path(folder, 1).exists())

    def test_the_shared_words_are_pinned(self) -> None:
        game, folder, old = self.make("huttest", 1, "Modded")
        source = cs.read_slots(game, folder).sources[0]
        self.assertEqual(
            window.move_replace_text(folder, source, 2, "Old Village", NOW),
            f"Save 2 holds the Old Village village. It will be replaced by {old}, moved from Save 1 with all its "
            f"files. The whole save folder ({folder}) is backed up first, and Old Village's files are kept in "
            "Backups\\2026-10-31 1200 S2. Replace it?")
        self.assertEqual(ms.BACKUP_LABEL, "(before move)")
        self.assertEqual(ms.SET_ASIDE_PREFIX, "Replaced by move ")
        self.assertEqual(window.MOVE_TITLE, "Move Player Slot")


class PreviewKeyTests(unittest.TestCase):
    """The preview: No is the default; Return and Escape answer No; only Yes moves."""

    def setUp(self) -> None:
        self.root = tc._tk_root()
        if self.root is None:
            self.skipTest("no Tk display")

    def tearDown(self) -> None:
        self.root.destroy()

    def answer(self, act) -> bool:
        top, answer = window.build_preview(self.root, "Move Player Slot", "Move?", ["a  ->  b"] * 200)
        self.root.update()
        act(top)
        self.root.update()
        return answer["yes"]

    def test_return_escape_and_closing_answer_no(self) -> None:
        self.assertFalse(self.answer(lambda top: top.event_generate("<Return>")))
        self.assertFalse(self.answer(lambda top: top.event_generate("<Escape>")))
        self.assertFalse(self.answer(lambda top: top.tk.eval(top.protocol("WM_DELETE_WINDOW"))))
        self.assertFalse(self.answer(lambda top: top.no_button.invoke()))
        self.assertTrue(self.answer(lambda top: top.yes_button.invoke()))

    def test_no_is_the_default_and_the_list_scrolls_within_the_screen(self) -> None:
        top, _answer = window.build_preview(self.root, "Move Player Slot", "Move?", ["x" * 300] * 500)
        self.root.update()
        self.assertEqual(str(top.no_button.cget("default")), "active")
        self.assertEqual(str(top.listing.cget("state")), "disabled")
        self.assertLessEqual(top.winfo_reqheight(), top.winfo_screenheight())
        self.assertLessEqual(top.winfo_reqwidth(), top.winfo_screenwidth())
        top.destroy()


class GuiWiringTests(unittest.TestCase):
    def test_the_copy_window_offers_move(self) -> None:
        source = (ROOT / "src" / "vv_copy_slot_window.py").read_text(encoding="utf-8")
        body = source[source.index("def open_copy_slot("):]
        self.assertIn('value="move"', body)
        self.assertIn("confirm_and_move(\n                ask_yes_no, ask_preview,", body)
        self.assertNotIn("vv_move_slot.move_slot(", body)        # only through the questions
        self.assertIn('"Move..." if move else "Copy..."', body)


import unittest.mock  # noqa: E402  (used above)

if __name__ == "__main__":
    unittest.main()
