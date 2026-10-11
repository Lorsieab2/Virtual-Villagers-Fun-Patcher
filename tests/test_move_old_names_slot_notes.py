"""Move Old Files to New Names writes its note where the repairs of each village are written.

Repair records about one village go in that village's own "Logs\\Save <n>\\Repairs Made"
(src/vv_log_tools.py repair_record_start); a record about the whole save folder goes in the shared
"Repairs Made".  The move is the save folder's, so the shared record stays (its header says "all
villages in this save folder"); every save slot whose files it moved or combined (a name ending
"- Save <n>") also gets its own short record, naming that slot's files (all five games).
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_move_old_names as mv  # noqa: E402
import vv_save_layout as layout  # noqa: E402

DATA, LOGS = layout.DATA, layout.LOGS
NOW = datetime(2026, 10, 10, 20, 0, 0)
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}


class Processes:
    def find(self, exe_name):
        return []


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("latin-1") if isinstance(data, str) else data)


class SlotNoteTests(unittest.TestCase):
    def folder(self, tmp: str, game: int) -> Path:
        f = Path(tmp) / f"Virtual Villagers - {TITLES[game]} - Modded"
        write(f / "VirtualVillagers1.ldw", b"save")
        return f

    def test_each_slot_whose_files_moved_gets_a_note_in_its_own_repairs_made(self) -> None:
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as tmp:
                f = self.folder(tmp, game)
                write(f / DATA / "Cross-Check" / f"Virtual Villagers {game} Cross-Check - Save 1.dat", b"one")
                write(f / DATA / "Cross-Check" / f"Virtual Villagers {game} Cross-Check - Save 3.dat", b"three")
                write(f / DATA / "Cross-Check" / f"Virtual Villagers {game} Repair Approved - Save 3.dat", b"x")
                write(f / DATA / "Log Words" / f"Virtual Villagers {game} Log Words.dat", b"0\tx\r\n")
                write(f / LOGS / "Births and Conceptions" / f"Virtual Villagers {game} Births and Conceptions Log 1.txt",
                      "Village: Hut (Save 1)\r\n")
                result = mv.move_old_files(f, Processes(), NOW)
                self.assertEqual(result.slot_notes, [1, 3])
                stem = f"Virtual Villagers {game} Repairs Log 1.txt"
                one = (f / LOGS / "Save 1" / "Repairs Made" / stem).read_bytes().decode("latin-1")
                three = (f / LOGS / "Save 3" / "Repairs Made" / stem).read_bytes().decode("latin-1")
                self.assertIn("Cross-Check - Save 1.dat", one)
                self.assertNotIn("Save 3.dat", one, "a slot's note names only its own files")
                self.assertIn("Cross-Check - Save 3.dat", three)
                self.assertIn("Repair Approved - Save 3.dat", three)
                self.assertIn("Village: Hut (Save 1)\r\nRepair ", one, "the village's own header when its log is there")
                self.assertIn("Village: (Save 3)\r\nRepair ", three, "else the slot's")
                self.assertFalse((f / LOGS / "Save 2").exists(), "a slot with none of its files moved gets nothing")
                shared = (f / LOGS / "Repairs Made" / stem).read_bytes().decode("latin-1")
                self.assertIn("Village: (all villages in this save folder)\r\nRepair ", shared,
                              "the whole move is still in the shared log")
                numbers = sorted(int(line[7:]) for text in (one, three, shared) for line in text.split("\r\n")
                                 if line.startswith("Repair ") and line[7:].isdigit())
                self.assertEqual(len(numbers), len(set(numbers)), "numbers continue per game: none twice")

    def test_a_move_with_no_slot_files_writes_only_the_shared_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = self.folder(tmp, 1)
            write(f / DATA / "Log Words" / "Virtual Villagers 1 Log Words.dat", b"0\tx\r\n")
            result = mv.move_old_files(f, Processes(), NOW)
            self.assertEqual(result.slot_notes, [])
            self.assertFalse(any((f / LOGS).glob("Save */Repairs Made/*")))
            self.assertTrue((f / LOGS / "Repairs Made" / "Virtual Villagers 1 Repairs Log 1.txt").is_file())

    def test_slots_involved_reads_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = self.folder(tmp, 1)
            write(f / DATA / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 2.dat", b"p")
            write(f / DATA / "Parentage Records" / "Virtual Villagers 1 Parentage Records - Save 5.dat", b"p")
            before = sorted(p.relative_to(f).as_posix() for p in f.rglob("*"))
            found = mv.slots_involved(f, mv.plan(f))
            self.assertEqual(sorted(found), [2, 5])
            self.assertEqual(sorted(p.relative_to(f).as_posix() for p in f.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
