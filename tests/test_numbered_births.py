"""Birth records are numbered like Conceptions: "Birth <n>" (the owner, 2026-10-09, v1.35.66).

The exporter writes "Birth <n>", the running count of the Birth records already in the game's
Births and Conceptions files (native/parentage_export count_running_records, birth_heading.h);
every reader takes both "Birth <n>" and an older log's plain "Birth"; Repair Saves & Logs offers to
number the older ones (src/vv_log_additions.py plan_birth_numbers), backed up first, through a
temporary file, with the Like and Dislike Words boundary moved with the bytes it adds.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
BIRTHS = "Births and Conceptions/Virtual Villagers {game} Births and Conceptions Log {n}.txt"


def birth(child: str, heading: str = "Birth", mother: str = "Ma") -> str:
    return (f"{heading}\n  Child: {child}\n    Sex: Female\n    Head: 3\n    Body: 4\n    Likes: (none)\n"
            f"    Dislikes: (none)\n  Mother: {mother}\n    Head: 1\n    Body: 1\n  Father: Pa\n    Head: 2\n"
            f"    Body: 2\n\n")


def conception(n: int, mother: str = "Ma") -> str:
    return (f"Conception {n}\n  Mother: {mother}\n    Age at conception: 400\n    Head: 1\n    Body: 1\n"
            f"  Father: Pa\n    Age at conception: 400\n    Head: 2\n    Body: 2\n  Babies in pregnancy: 1\n\n")


def write(folder: Path, relative: str, text: str) -> Path:
    path = folder / LOGS / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return path


def headings(path: Path) -> list[str]:
    return [line for line in path.read_bytes().decode("latin-1").split("\r\n") if line.startswith("Birth")]


class Readers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.checker = tools.load_checker()

    def tearDown(self):
        self.tmp.cleanup()

    def test_both_headings_are_birth_records(self):
        for text in ("Birth", "Birth 1", "Birth 86", " Birth 7 "):
            self.assertTrue(self.checker.is_birth_heading(text), text)
            self.assertTrue(additions.is_birth(text.strip()), text)
        for text in ("Births", "Birth x", "Birth 1a", "Birth ", "Birthday 3", "Conception 1", "  Child: Birth"):
            self.assertFalse(self.checker.is_birth_heading(text) and text.strip() != "Birth", text)
            self.assertFalse(additions.is_birth(text) and text.strip() != "Birth", text)

    def test_the_births_log_reads_old_and_numbered_records_alike(self):
        write(self.folder, BIRTHS.format(game=2, n=1),
              "Village: Tribe (Save 1)\n" + conception(1) + birth("Old") + conception(2) + birth("New", "Birth 2"))
        records, _files = self.checker.births_log(self.folder, 2, 1)
        self.assertEqual([(r.kind, r.child.name if r.child else r.mother.name) for r in records],
                         [("conception", "Ma"), ("birth", "Old"), ("conception", "Ma"), ("birth", "New")])
        self.assertFalse(records.damaged)

    def test_the_sex_line_reader_takes_a_numbered_birth(self):
        people = self.checker._block_people(birth("Kid", "Birth 5").rstrip("\n").split("\n"))
        self.assertEqual([p["name"] for p in people], ["Kid"], "only the child of a Birth record")

    def test_born_as_reads_numbered_births(self):
        write(self.folder, BIRTHS.format(game=3, n=1),
              "Village: Tribe (Save 1)\n" + conception(1).replace("pregnancy: 1", "pregnancy: 2")
              + birth("A", "Birth 1") + birth("B", "Birth 2"))
        kind = {k.id: k for k in additions.plan(self.folder, 3, 1)}["born_as"]
        self.assertEqual(kind.decided, 2, "a twin pair of numbered Birth records")


class Repair(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def number(self, game=2, slot=1):
        kind = {k.id: k for k in additions.plan(self.folder, game, slot)}["birth_numbers"]
        return kind, additions.apply(self.folder, [kind], {"birth_numbers"}, {})

    def test_unnumbered_births_are_numbered_in_order(self):
        log = write(self.folder, BIRTHS.format(game=2, n=1),
                    "Village: Tribe (Save 1)\n" + conception(1) + birth("A") + conception(2) + birth("B")
                    + birth("C"))
        before = log.read_bytes()
        kind, done = self.number()
        self.assertEqual(kind.decided, 3)
        self.assertEqual(headings(log), ["Birth 1", "Birth 2", "Birth 3"])
        # Everything else in the record is exactly as it was.
        self.assertEqual(log.read_bytes().replace(b"Birth 1\r\n", b"Birth\r\n").replace(b"Birth 2\r\n", b"Birth\r\n")
                         .replace(b"Birth 3\r\n", b"Birth\r\n"), before)
        [fix] = done["birth_numbers"]
        self.assertEqual(fix.count, 3)
        copy = self.folder / DATA / "Copies Made Before Repairs" / LOGS / "Births and Conceptions" / fix.backup
        self.assertEqual(copy.read_bytes(), before, "the log was copied first")
        self.assertFalse(log.with_name(log.name + ".tmp").exists())
        # Recorded in the Repairs Made log as Repair Saves & Logs records every addition.
        tools.note_word_repair(self.folder, 2, "Village: Tribe (Save 1)", done["birth_numbers"],
                               checked=additions.CHECKED["birth_numbers"], corrected=additions.ADDED["birth_numbers"])
        [repairs] = (self.folder / LOGS).rglob("Virtual Villagers 2 Repairs Log 1.txt")
        text = repairs.read_bytes().decode("latin-1")
        self.assertIn("Repair 1\r\n", text)
        self.assertIn(f"  Birth number added: {fix.name} -- 3 villager(s)\r\n", text)
        self.assertIn(f"  Backup: {fix.backup}\r\n", text)

    def test_numbered_ones_after_them_are_continued_and_kept(self):
        # An older build wrote 2 Births; this build then wrote "Birth 3" (it counts both kinds).
        log = write(self.folder, BIRTHS.format(game=2, n=1),
                    "Village: Tribe (Save 1)\n" + birth("A") + birth("B") + birth("C", "Birth 3"))
        kind, _done = self.number()
        self.assertEqual(kind.decided, 2)
        self.assertEqual(headings(log), ["Birth 1", "Birth 2", "Birth 3"])

    def test_an_unnumbered_one_after_a_numbered_one_follows_it(self):
        log = write(self.folder, BIRTHS.format(game=2, n=1),
                    "Village: Tribe (Save 1)\n" + birth("A") + birth("B", "Birth 2") + birth("C") + birth("D"))
        self.number()
        self.assertEqual(headings(log), ["Birth 1", "Birth 2", "Birth 3", "Birth 4"])

    def test_an_already_numbered_log_is_left_alone(self):
        log = write(self.folder, BIRTHS.format(game=2, n=1),
                    "Village: Tribe (Save 1)\n" + birth("A", "Birth 1") + birth("B", "Birth 2"))
        before = log.read_bytes()
        kind, done = self.number()
        self.assertEqual(kind.decided, 0)
        self.assertEqual(done, {})
        self.assertEqual(log.read_bytes(), before)
        self.assertFalse((self.folder / DATA / "Copies Made Before Repairs").exists(), "nothing copied")

    def test_the_count_runs_on_across_the_numbered_files(self):
        first = write(self.folder, BIRTHS.format(game=4, n=1),
                      "Village: Tribe (Save 1)\n" + birth("A") + birth("B"))
        second = write(self.folder, BIRTHS.format(game=4, n=2),
                       "Village: Tribe (Save 1)\n" + birth("C") + birth("D", "Birth 4") + birth("E"))
        kind, done = self.number(game=4)
        self.assertEqual(kind.decided, 4)
        self.assertEqual(headings(first), ["Birth 1", "Birth 2"])
        self.assertEqual(headings(second), ["Birth 3", "Birth 4", "Birth 5"])
        self.assertEqual(sorted(f.count for f in done["birth_numbers"]), [2, 2])

    def test_another_villages_births_count_but_are_not_changed(self):
        # The exporter's count runs over every village in the game's files (like a Conception's).
        log = write(self.folder, BIRTHS.format(game=5, n=1),
                    "Village: Other (Save 2)\n" + birth("X") + "Village: Tribe (Save 1)\n" + birth("A"))
        self.number(game=5)
        self.assertEqual(headings(log), ["Birth", "Birth 2"])
        self.number(game=5, slot=2)
        self.assertEqual(headings(log), ["Birth 1", "Birth 2"])

    def test_the_like_and_dislike_words_boundary_moves_with_the_added_bytes(self):
        old = "Village: Tribe (Save 1)\n" + birth("A") + birth("B")
        log = write(self.folder, BIRTHS.format(game=1, n=1), old + birth("C", "Birth 3"))
        boundary = len(old.replace("\n", "\r\n").encode("latin-1"))
        name = f"{LOGS}\\Births and Conceptions\\{log.name}"
        dat = self.folder / DATA / "Like and Dislike Words" / "Virtual Villagers 1 Log Words.dat"
        dat.parent.mkdir(parents=True)
        dat.write_bytes(f"{boundary}\t{name}\r\n".encode("utf-8"))
        self.number(game=1)
        text = log.read_bytes()
        bounds = tools.load_checker().word_boundaries(self.folder, 1)
        moved = bounds[name.lower()]
        self.assertEqual(moved, boundary + 4, "two \" <n>\" added before it")
        self.assertTrue(text[moved:].startswith(b"Birth 3\r\n"), "still where this build's text begins")

    def test_a_boundary_of_zero_or_none_is_left_as_it_is(self):
        log = write(self.folder, BIRTHS.format(game=1, n=1), "Village: Tribe (Save 1)\n" + birth("A"))
        name = f"{LOGS}\\Births and Conceptions\\{log.name}"
        dat = self.folder / DATA / "Like and Dislike Words" / "Virtual Villagers 1 Log Words.dat"
        dat.parent.mkdir(parents=True)
        dat.write_bytes(f"0\t{name}\r\n".encode("utf-8"))
        self.number(game=1)
        self.assertEqual(dat.read_bytes(), f"0\t{name}\r\n".encode("utf-8"))

    def test_lines_added_by_other_kinds_move_the_boundary_too(self):
        old = "Village: Tribe (Save 1)\n" + conception(1).replace("pregnancy: 1", "pregnancy: 2") \
            + birth("A") + birth("B")
        log = write(self.folder, BIRTHS.format(game=3, n=1), old + birth("C", "Birth 3", mother="Mo"))
        boundary = len(old.replace("\n", "\r\n").encode("latin-1"))
        name = f"{LOGS}\\Births and Conceptions\\{log.name}"
        dat = self.folder / DATA / "Like and Dislike Words" / "Virtual Villagers 3 Log Words.dat"
        dat.parent.mkdir(parents=True)
        dat.write_bytes(f"{boundary}\t{name}\r\n".encode("utf-8"))
        kinds = additions.plan(self.folder, 3, 1)
        additions.apply(self.folder, kinds, {"born_as", "birth_numbers"}, {})
        moved = tools.load_checker().word_boundaries(self.folder, 3)[name.lower()]
        self.assertTrue(log.read_bytes()[moved:].startswith(b"Birth 3\r\n"))
        self.assertEqual(log.read_bytes().count(b"  Born as: Twin\r\n"), 2)

    def test_a_golden_childs_birth_added_in_the_same_repair_is_numbered(self):
        arrived = ("Arrived 1\n  Name: Lulu\n  Special villager: Golden Child\n  Age: 100\n  Sex: Female\n"
                   "  Head: 5\n  Body: 5\n  Likes: (none)\n  Dislikes: (none)\n\n")
        log = write(self.folder, BIRTHS.format(game=1, n=1),
                    "Village: Tribe (Save 1)\n" + birth("A") + conception(1) + arrived + birth("B"))
        kinds = {k.id: k for k in additions.plan(self.folder, 1, 1)}
        [question] = kinds["golden"].questions.values()
        done = additions.apply(self.folder, list(kinds.values()), {"golden", "birth_numbers"},
                               {question.key: question.options[0]})
        self.assertEqual(headings(log), ["Birth 1", "Birth 2", "Birth 3"])
        text = log.read_bytes().decode("latin-1")
        self.assertIn("Birth 2\r\n  Child: Lulu\r\n", text)
        self.assertEqual(done["birth_numbers"][0].count, 3)


if __name__ == "__main__":
    unittest.main()
