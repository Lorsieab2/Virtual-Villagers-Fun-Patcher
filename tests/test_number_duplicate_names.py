"""Number Duplicate Names (src/vv_number_names.py, vv_genealogy.duplicate_names, the Family Tree Maker).

The owner (2026-10-07): "How about a "Number duplicate names" button in the family tree maker and repair
logs?  If there are duplicate "Soda"s, name the first one "Soda I", and the second one "Soda II" etc.
Also offer to edit the save files."
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_number_names as nn  # noqa: E402
import test_last_names_rename as fixture  # noqa: E402
from test_last_names_rename import NOW, STRIDE, TABLE, NoGame, Running, entry  # noqa: E402


def village(*people: gen.Person) -> gen.Village:
    return gen.Village(3, 1, "Tribe", {p.id: p for p in people})


class TheNumbers(unittest.TestCase):
    def test_roman_numerals_go_on_past_twenty(self):
        self.assertEqual([gen.roman(n) for n in (1, 2, 4, 9, 14, 20, 21, 40, 99)],
                         ["I", "II", "IV", "IX", "XIV", "XX", "XXI", "XL", "XCIX"])

    def test_the_oldest_namesake_is_the_first_and_the_dead_count(self):
        v = village(gen.Person(1, "Soda", 1, 1, sex="Male", age=300, alive=True, birth_record=5),
                    gen.Person(2, "Soda", 2, 2, sex="Male", age=900, gone="died", birth_record=1),
                    gen.Person(3, "Soda", 3, 3, sex="Female", age=500, alive=True, birth_record=3),
                    gen.Person(4, "Mai", 4, 4, sex="Female", age=500, alive=True),
                    gen.Person(5, "Upcoming child", -1, -1, upcoming=True),
                    gen.Person(6, "Upcoming child", -1, -1, upcoming=True))
        self.assertEqual(gen.duplicate_names(v), {2: "Soda I", 3: "Soda II", 1: "Soda III"})

    def test_namesakes_who_look_the_same_or_have_no_looks_or_no_room_keep_their_names(self):
        long = "Abcdefghijklmnopqrstu"                        # 21 letters: + " II" is 24, past 23
        v = village(gen.Person(1, "Twin", 5, 5, alive=True), gen.Person(2, "Twin", 5, 5, alive=True),
                    gen.Person(3, "Ghost", None, None), gen.Person(4, "Ghost", 6, 6, alive=True),
                    gen.Person(5, long, 7, 7, alive=True), gen.Person(6, long, 8, 8, alive=True))
        out = nn.numbering(v)
        self.assertEqual(out.renames, {("Ghost", 6, 6): "Ghost II", (long, 7, 7): f"{long} I"})
        self.assertEqual(len(out.notes), 3)


class TheTree(unittest.TestCase):
    def test_the_tree_shows_them_numbered_only_when_asked_and_remembers_it(self):
        v = village(gen.Person(1, "Soda", 1, 1, sex="Male", age=900, alive=True, birth_record=1),
                    gen.Person(2, "Soda", 2, 2, sex="Male", age=300, alive=True, birth_record=2))
        gen.number_people(v)
        plain = ft.layout(v, ft.Edits())
        self.assertEqual(ft.default_text(plain, v.people[2])[0], "2. Soda")
        edits = ft.Edits(number_names=True)
        numbered = ft.layout(v, edits)
        self.assertEqual(ft.default_text(numbered, v.people[1])[0], "1. Soda I")
        self.assertEqual(ft.default_text(numbered, v.people[2])[0], "2. Soda II")
        self.assertTrue(ft.Edits.from_data(edits.to_data()).number_names)
        self.assertFalse(ft.Edits.from_data({}).number_names)


class InTheSaveAndTheLogs(unittest.TestCase):
    """A living Soda, a dead Soda (other looks) and a living Soda's child, on Last Names' little save."""
    _log = fixture.GiveLastNames._log
    tearDown = fixture.GiveLastNames.tearDown

    def setUp(self):
        fixture.GiveLastNames.setUp(self)
        people = [entry("Soda", 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8),
                  entry("Kid", 0, 50, 9, 9, father=("Soda", 5, 6), mother=("Aipi", 7, 8)),
                  entry("Orphan", 1, 2, 3, 3, father=("Soda", 1, 1))]
        self.save.write_bytes(b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))
        for path in (self.history, self.births, self.deaths):
            path.write_bytes(path.read_bytes().replace(b"Ago", b"Soda").replace(b"Child: Aipi", b"Child: Lani"))

    def test_every_soda_is_numbered_in_the_save_and_every_log(self):
        want = nn.numbering(gen.load_village(self.folder, 3, 1))
        living, dead = want.renames[("Soda", 5, 6)], want.renames[("Soda", 1, 1)]
        self.assertEqual({living, dead}, {"Soda I", "Soda II"})
        nn.number_names(self.folder, 3, 1, NoGame(), NOW)
        self.assertEqual([v.name for v in ln.living(self.folder, 3, 1)], [living, "Aipi", "Kid", "Orphan"])
        data = self.save.read_bytes()
        kid, orphan = TABLE + 2 * STRIDE + 0x14, TABLE + 3 * STRIDE + 0x14
        self.assertEqual(data[kid + 0x24:kid + 0x24 + len(living) + 1], living.encode() + b"\0")
        self.assertEqual(data[orphan + 0x24:orphan + 0x24 + len(dead) + 1], dead.encode() + b"\0",
                         "a dead parent is numbered too")
        self.assertIn(f"    Father: {living}\r\n      Head: 5", self.history.read_bytes().decode())
        self.assertIn(f"  Father: {living}\r\n", self.births.read_bytes().decode())
        self.assertIn(f"  Name: {dead}\r\n", self.deaths.read_bytes().decode(), "the dead's own records too")
        self.assertFalse(gen.duplicate_names(gen.load_village(self.folder, 3, 1)))

    def test_it_is_refused_while_the_game_runs_or_when_no_name_is_shared(self):
        before = self.save.read_bytes()
        with self.assertRaises(Exception):
            nn.number_names(self.folder, 3, 1, Running(), NOW)
        self.assertEqual(self.save.read_bytes(), before)
        nn.number_names(self.folder, 3, 1, NoGame(), NOW)
        with self.assertRaises(ln.LastNamesError):
            nn.number_names(self.folder, 3, 1, NoGame(), NOW)


class TheWindows(unittest.TestCase):
    def test_the_tree_maker_and_repair_logs_offer_it(self):
        tree = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        self.assertIn('ttk.Button(tab, text="Number duplicate names", command=self._number_names)', tree)
        self.assertIn('("Number Duplicate Names...", "", self._number_names)', tree)
        offer = tree[tree.index("    def _number_names(self)"):tree.index("    def _reset_frames(self)")]
        self.assertLess(offer.index("messagebox.askyesno("), offer.index("vv_number_names.number_names("),
                        "the save is edited only when the player says so")
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        checklist = gui[gui.index("    def _repair_checklist("):gui.index("    def _repair_questions(")]
        self.assertIn("number_var = tk.BooleanVar(value=False)", checklist, "never ticked for the player")
        repair = gui[gui.index("    def _repair_logs("):gui.index("    def _repair_checklist(")]
        self.assertIn("lambda: vv_number_names.number_names(folder, number, info.slot)", repair)
        self.assertLess(repair.index("vv_last_names.give_last_names("), repair.index("vv_number_names.number_names("),
                        "numbered after any last names are given")


if __name__ == "__main__":
    unittest.main()
