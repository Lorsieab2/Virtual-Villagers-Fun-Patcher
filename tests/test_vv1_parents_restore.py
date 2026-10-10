"""Repair Saves & Logs' "Restore A New Home Parents..." (src/vv1_parents_restore.py).

v1.35.66 and v1.35.67 could write an empty parents table over A New Home's parentage file (the title
screen's seeded founders; native/vv1_parentage, fixed in v1.35.68).  The copies the patcher kept of the
file give the parents back -- only ever adding: an entry with a parent now is never changed, a pregnancy's
expected father is never touched, an arrival never gets parents, an old name (before Last Names or a
rename) is never brought back, and a copy the Births log contradicts is not used.  All synthetic files
in a temporary folder."""
from __future__ import annotations

import os
import shutil
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv1_parents_restore as restore  # noqa: E402
import vv_log_tools as tools  # noqa: E402

SLOT = 1
NAME = 28


def _name(text: str) -> bytes:
    return text.encode("latin-1").ljust(NAME, b"\0")


def table(rows: list[tuple]) -> bytes:
    """rows: (index, name, gender, scalar, head, body, departed, father, mother, stash)."""
    data = bytearray(restore.SIZE)
    data[:4] = restore.MAGIC
    struct.pack_into("<I", data, 8, SLOT)
    for index, name, gender, scalar, head, body, departed, father, mother, stash in rows:
        o = restore.HEADER + index * restore.OCCUPANT
        data[o:o + 4] = bytes([gender, departed, head + 1, body + 1])
        struct.pack_into("<i", data, o + 4, scalar)
        data[o + 8:o + 36] = _name(name)
        e = restore.HEADER + restore.COUNT * restore.OCCUPANT + index * restore.ENTRY
        if father:
            data[e:e + 2] = bytes([3, 4])
            data[e + 8:e + 36] = _name(father)
        if mother:
            data[e + 2:e + 4] = bytes([5, 6])
            data[e + 36:e + 64] = _name(mother)
        if stash:
            data[e + 4:e + 6] = bytes([7, 8])
            data[e + 64:e + 92] = _name(stash)
    return bytes(data)


def parents(data: bytes, who: str) -> tuple[str, str, str, int] | None:
    t = restore.Table(bytearray(data))
    for i in range(restore.COUNT):
        if t.identity(i) and t.identity(i)[0] == who:
            e = t.entry_at(i)
            stash = restore._cstr(t.data, e + 64)
            return (*t.names(i), stash, t.occupant(i)[1])
    return None


class Idle:
    def find(self, exe):
        return []


class Running:
    def find(self, exe):
        return [1234]


LOG_HEADER = "Village: Test Tribe (Save 1)\n"


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.folder = self.root / "Virtual Villagers - Test"
        records = self.folder / "Virtual Villagers Fun Patcher Data" / "Parentage Records"
        records.mkdir(parents=True)
        self.path = records / restore.file_name(SLOT)
        # The table v1.35.67 left: everyone's parents gone; Bram's set again since (a newer real change);
        # Alba expecting by Dax (this session's conception); Fatai departed this session.
        self.path.write_bytes(table([
            (0, "Alba Bahati", 2, 13, 4, 5, 0, None, None, "Dax"),
            (1, "Bram Bahati", 1, 11, 2, 3, 0, "Newer Father", "Newer Mother", None),
            (2, "Cleo Bahati", 2, 13, 6, 7, 0, None, None, None),
            (3, "Silko Akikai", 1, 5, 8, 9, 0, None, None, None),
            (4, "Fatai Alosaka", 2, 50, 10, 11, 1, None, None, None),
        ]))
        older = self.path.with_name(self.path.name + ".before-v1.35.58-repair")
        older.write_bytes(table([
            (0, "Alba Bahati", 2, 13, 4, 5, 0, "Bram Bahati", "Cora Bahati", "Old Stash"),
            (1, "Bram Bahati", 1, 11, 2, 3, 0, "Old Father", "Old Mother", None),
            (2, "Cleo Bahati", 2, 13, 6, 7, 0, "Bram Bahati", "Cora Bahati", None),
            (3, "Silko Akikai", 1, 5, 8, 9, 0, "Ghali Bahati", "Onawa Jumapili", None),
            (4, "Fatai Alosaka", 2, 50, 10, 11, 0, "Ponui Alosaka", "Hawa Bahati", None),
            (5, "Dana Wanjiko", 2, 50, 1, 1, 0, "Howi Wanjiko", "Pupa Bahati", None),
            (6, "Al", 2, 13, 4, 5, 0, "Bram", "Cora", None),
        ]))
        newer = self.path.with_name(self.path.name + ".before-v1.35.58-repair-2")
        newer.write_bytes(table([(0, "Alba Bahati", 2, 13, 4, 5, 0, None, None, None)]))
        past = time.time() - 3600
        os.utime(older, (past, past))
        logs = self.folder / "Virtual Villagers Fun Patcher Logs"
        births = logs / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt"
        births.parent.mkdir(parents=True)
        births.write_text(
            LOG_HEADER
            + "Birth 1\n  Child: Alba Bahati\n    Sex: Female\n    Head: 4\n    Body: 5\n  Skills:\n    Farming 1\n"
              "  Mother: Cora Bahati\n    Head: 1\n    Body: 1\n  Father: Bram Bahati\n    Head: 2\n    Body: 2\n"
              "  Born as: Single birth\n\n"
            + "Birth 2\n  Child: Cleo Bahati\n    Sex: Female\n    Head: 6\n    Body: 7\n  Skills:\n    Farming 1\n"
              "  Mother: Eda Bahati\n    Head: 1\n    Body: 1\n  Father: Dax Bahati\n    Head: 2\n    Body: 2\n"
              "  Born as: Single birth\n\n"
            + "Arrived 1\n  Name: Silko Akikai\n  How: The Bachelors\n\n", encoding="latin-1")
        deaths = logs / "Deaths and Disappearances" / "Virtual Villagers 1 Deaths Log 1.txt"
        deaths.parent.mkdir(parents=True)
        deaths.write_text(LOG_HEADER + "Death 1\n  Name: Dana Wanjiko\n  Age at death: 1600\n\n"
                          "Death 2\n  Name: Fatai Alosaka\n  Age at death: 1663\n\n", encoding="latin-1")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_only_ever_adds(self):
        result = restore.restore(self.folder, SLOT, processes=Idle())
        data = self.path.read_bytes()
        self.assertEqual(parents(data, "Alba Bahati")[:3], ("Bram Bahati", "Cora Bahati", "Dax"),
                         "Alba's parents come back from the newest copy that has them; her stash is untouched")
        self.assertEqual(parents(data, "Bram Bahati")[:2], ("Newer Father", "Newer Mother"),
                         "an entry with parents now is never changed")
        self.assertEqual(parents(data, "Fatai Alosaka")[:2], ("Ponui Alosaka", "Hawa Bahati"),
                         "a villager who died this session keeps her parents")
        dana = parents(data, "Dana Wanjiko")
        self.assertEqual(dana[:2], ("Howi Wanjiko", "Pupa Bahati"))
        self.assertEqual(dana[3], 1, "a dead villager the file had dropped comes back as departed")
        self.assertIsNone(parents(data, "Al"), "an old name with no Death record is never brought back")
        self.assertEqual(parents(data, "Silko Akikai")[:2], ("", ""), "an arrival never gets parents")
        self.assertEqual(parents(data, "Cleo Bahati")[:2], ("", ""), "a copy the Births log contradicts is not used")
        self.assertTrue(any("Cleo Bahati" in c for c in result.plan.conflicts))
        self.assertEqual(result.copy.read_bytes()[:4], restore.MAGIC)
        self.assertIn("Copies Made Before Repairs", str(result.copy))
        note = (self.folder / "Virtual Villagers Fun Patcher Logs" / "Repairs Made"
                / "Virtual Villagers 1 Repairs Log 1.txt").read_text("latin-1")
        self.assertIn("Village: Test Tribe (Save 1)", note)
        self.assertIn("Parents restored: Alba Bahati: father Bram Bahati, mother Cora Bahati", note)
        self.assertIn("Parents restored: Dana Wanjiko (departed)", note)
        self.assertEqual(note.count("  Backup: "), 1)

    def test_a_second_run_changes_nothing(self):
        restore.restore(self.folder, SLOT, processes=Idle())
        once = self.path.read_bytes()
        again = restore.restore(self.folder, SLOT, processes=Idle())
        self.assertEqual(again.plan.restored, [])
        self.assertEqual(self.path.read_bytes(), once)

    def test_refused_while_the_game_runs(self):
        before = self.path.read_bytes()
        with self.assertRaises(tools.GameRunning):
            restore.restore(self.folder, SLOT, processes=Running())
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
