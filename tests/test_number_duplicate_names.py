"""Number Duplicate Names (src/vv_number_names.py, vv_genealogy.duplicate_names, the Family Tree Maker).

The owner (2026-10-07): "How about a "Number duplicate names" button in the family tree maker and repair
logs?  If there are duplicate "Soda"s, name the first one "Soda I", and the second one "Soda II" etc.
Also offer to edit the save files."
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

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

    def test_the_first_to_appear_is_the_first_unless_the_player_says_otherwise(self):
        # The owner, 2026-10-07: "make "in order of appearance" default" (in the logs, so the dead
        # and missing are numbered too).  Oldest first counts the dead by their age at death; an
        # unknown age comes last.
        v = village(gen.Person(1, "Soda", 1, 1, sex="Male", age=300, alive=True, birth_record=1),
                    gen.Person(2, "Soda", 2, 2, sex="Male", age=900, gone="died", birth_record=3),
                    gen.Person(3, "Soda", 3, 3, sex="Female", age=500, alive=True, birth_record=2),
                    gen.Person(7, "Soda", 7, 7, birth_record=0),
                    gen.Person(4, "Mai", 4, 4, sex="Female", age=500, alive=True),
                    gen.Person(5, "Upcoming child", -1, -1, upcoming=True),
                    gen.Person(6, "Upcoming child", -1, -1, upcoming=True))
        self.assertEqual(gen.duplicate_names(v), {7: "Soda I", 1: "Soda II", 3: "Soda III", 2: "Soda IV"})
        self.assertEqual(gen.duplicate_names(v, "oldest"), {2: "Soda I", 3: "Soda II", 1: "Soda III", 7: "Soda IV"})
        self.assertEqual(gen.duplicate_names(v, "youngest"), {1: "Soda I", 3: "Soda II", 2: "Soda III", 7: "Soda IV"})
        self.assertEqual(gen.duplicate_names(v, "appearance"), {7: "Soda I", 1: "Soda II", 3: "Soda III", 2: "Soda IV"})

    def test_namesakes_are_the_same_first_and_last_name_and_old_numbers_go(self):
        # The owner, 2026-10-08: "roman numerals should be given for people who have both the same first
        # and last name (Suki Wikimak I, Suki Wikimak II)"; "hawa bahati and hawa awanata are different
        # people ... Hawa awanata should not be called I or II unless there's literally a second hawa
        # awanata"; and with first names only, "Suki I and Suki II".
        v = village(gen.Person(1, "Suki Alosaka I", 1, 1, alive=True, birth_record=0),
                    gen.Person(2, "Suki Wanjiko II", 2, 2, alive=True, birth_record=1),
                    gen.Person(3, "Hawa Bahati I", 3, 3, alive=True, birth_record=2),
                    gen.Person(4, "Hawa Awanata II", 4, 4, alive=True, birth_record=3),
                    gen.Person(5, "Kaula Akikai", 5, 5, alive=True, birth_record=4),
                    gen.Person(6, "Kaula Akikai", 6, 6, alive=True, birth_record=5),
                    gen.Person(7, "Meka", 7, 7, alive=True, birth_record=6),
                    gen.Person(8, "Meka", 8, 8, alive=True, birth_record=7),
                    gen.Person(9, "Tomi Akikai II", 9, 9, alive=True, birth_record=8),
                    gen.Person(10, "Tomi Akikai", 10, 10, alive=True, birth_record=9))
        self.assertEqual(gen.duplicate_names(v), {
            1: "Suki Alosaka", 2: "Suki Wanjiko",               # no second Suki Alosaka or Suki Wanjiko
            3: "Hawa Bahati", 4: "Hawa Awanata",
            5: "Kaula Akikai I", 6: "Kaula Akikai II",          # the same first and last name
            7: "Meka I", 8: "Meka II",                           # first names only
            10: "Tomi Akikai I"})                                # Tomi Akikai II keeps his number
        self.assertEqual(gen.unnumbered("Soda II"), "Soda")
        self.assertEqual(gen.unnumbered("Ivi"), "Ivi")
        self.assertEqual(gen.unnumbered("Suki Wanjiko"), "Suki Wanjiko")

    def test_namesakes_who_look_the_same_or_have_no_looks_or_no_room_keep_their_names(self):
        long = "Abcdefghijklmnopqrstu"                        # 21 letters: + " II" is 24, past 23
        # The family tree sees the save's two same-looking Twins as one; the save's count tells.
        v = village(gen.Person(1, "Twin", 5, 5, alive=True), gen.Person(2, "Twin", 9, 9, alive=True),
                    gen.Person(3, "Ghost", None, None), gen.Person(4, "Ghost", 6, 6, alive=True),
                    gen.Person(5, long, 7, 7, alive=True), gen.Person(6, long, 8, 8, alive=True),
                    gen.Person(7, "Soda", 1, 1, alive=True))
        out = nn.numbering(v, alike={("Twin", 5, 5): 2}, nameless={"Soda", "Nobody", "Twin I"})
        # "Twin I" is a name-only record's: never given again, and the two Twins who look alike count as
        # two, II and III (Codex, #557).
        self.assertEqual(out.renames, {("Twin", 9, 9): "Twin IV", ("Ghost", 6, 6): "Ghost II",
                                       (long, 7, 7): f"{long} I"})
        self.assertEqual(len(out.notes), 4)
        self.assertTrue(any("2 living villagers are called Twin" in n for n in out.notes))
        self.assertTrue(any("Older records name a Soda without saying how they look" in n for n in out.notes))

    def test_a_record_with_other_looks_may_be_an_earlier_look(self):
        # Codex, #557: a namesake known only from records, neither alive nor dead, may be a living
        # one before Change Appearance -- that record keeps its name and is not counted.
        v = village(gen.Person(1, "Soda", 1, 1, alive=True, birth_record=1),
                    gen.Person(2, "Soda", 2, 2, alive=True, birth_record=2),
                    gen.Person(3, "Soda", 3, 3, birth_record=0))
        out = nn.numbering(v, order="appearance")
        self.assertEqual(out.renames, {("Soda", 1, 1): "Soda I", ("Soda", 2, 2): "Soda II"})
        self.assertTrue(any("Soda (head 3, body 3)" in n and "before Change Appearance" in n for n in out.notes))
        dead = village(gen.Person(1, "Soda", 1, 1, alive=True, birth_record=1),
                       gen.Person(3, "Soda", 3, 3, gone="died", birth_record=0))
        # A dead namesake is a separate villager: both are numbered (no age known: as they appeared).
        self.assertEqual(nn.numbering(dead).renames, {("Soda", 3, 3): "Soda I", ("Soda", 1, 1): "Soda II"})

    def test_look_alikes_count_and_names_in_the_patchers_files_are_taken(self):
        # Codex, #557 round 3: a look-alike pair is two villagers, so the next Soda is III; and a
        # "Soda IV" only the Village Elders names is never given again.
        v = village(gen.Person(1, "Soda", 1, 1, alive=True, birth_record=1),
                    gen.Person(2, "Soda", 2, 2, alive=True, birth_record=2),
                    gen.Person(3, "Soda", 3, 3, alive=True, birth_record=3))
        out = nn.numbering(v, alike={("Soda", 1, 1): 2}, taken={"Soda IV"}, order="appearance")
        self.assertEqual(out.renames, {("Soda", 2, 2): "Soda III", ("Soda", 3, 3): "Soda V"})

    def test_a_number_already_in_use_is_passed_over(self):
        v = village(gen.Person(1, "Soda", 1, 1, alive=True, birth_record=1),
                    gen.Person(2, "Soda", 2, 2, alive=True, birth_record=2),
                    gen.Person(3, "Soda I", 3, 3, alive=True, birth_record=3))
        self.assertEqual(gen.duplicate_names(v), {1: "Soda II", 2: "Soda III"})


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
        youngest = ft.Edits(number_names=True, number_order="youngest")
        self.assertEqual(ft.default_text(ft.layout(v, youngest), v.people[2])[0], "2. Soda I")
        self.assertEqual(ft.Edits.from_data(youngest.to_data()).number_order, "youngest")
        self.assertEqual(ft.Edits.from_data({"number_order": "nonsense"}).number_order, "appearance")


class InTheSaveAndTheLogs(unittest.TestCase):
    """A living Soda, a dead Soda (other looks) and a living Soda's child, on Last Names' little save."""
    _log = fixture.GiveLastNames._log
    tearDown = fixture.GiveLastNames.tearDown

    def setUp(self):
        fixture.GiveLastNames.setUp(self)
        # The made-up save holds no tribe name: say which village is this one.
        named = mock.patch("vv_log_additions.current_villages", return_value={"Village: Tribe (Save 1)"})
        named.start()
        self.addCleanup(named.stop)
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
        nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
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

    def test_look_alikes_in_the_save_and_name_only_lines_are_left_and_reported(self):
        people = [entry("Soda", 0, 1, 5, 6), entry("Soda", 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8),
                  entry("Aipi", 1, 50, 2, 2)]
        self.save.write_bytes(b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))
        self._log("Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 2.txt",
                  "Village: Tribe (Save 1)\nBirth\n  Child: Lani\n    Head: 4\n    Body: 4\n  Mother: Aipi\n\n")
        result, wanted = nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        self.assertEqual(sorted(v.name for v in ln.living(self.folder, 3, 1)), ["Aipi I", "Aipi II", "Soda", "Soda"])
        self.assertTrue(any("2 living villagers are called Soda" in n for n in wanted.notes))
        self.assertTrue(any("Log 2.txt names Aipi without saying which villager" in n for n in wanted.notes))

    def test_it_is_refused_when_the_village_cannot_be_told_apart(self):
        # Codex, #557: with the tribe name unread, an erased village's records would be counted.
        before = self.save.read_bytes()
        with mock.patch("vv_log_additions.current_villages", return_value=None):
            with self.assertRaises(ln.LastNamesError):
                nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        self.assertEqual(self.save.read_bytes(), before)

    def test_an_unburied_body_is_renamed_with_its_records(self):
        # Codex, #557: a namesake lying dead in the save is renamed there too, not only in the logs.
        people = [entry("Soda", 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8),
                  entry("Kid", 0, 50, 9, 9, father=("Soda", 5, 6), mother=("Aipi", 7, 8)),
                  entry("Soda", 0, 2, 4, 4, health=0)]
        self.save.write_bytes(b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))
        self.history.write_bytes(self.history.read_bytes()      # an earlier snapshot of the one now dead
                                 + b"Villager 3\r\n  Name: Soda\r\n  Head: 4\r\n  Body: 4\r\n\r\n")
        want = nn.numbering(gen.load_village(self.folder, 3, 1), *nn.evidence(self.folder, 3, 1))
        nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        body = TABLE + 3 * STRIDE + 0x14
        new = want.renames[("Soda", 4, 4)]
        self.assertEqual(self.save.read_bytes()[body:body + len(new) + 1], new.encode() + b"\0")

    def test_a_dead_namesake_who_looks_the_same_is_left_and_reported(self):
        # Codex, #557: the family tree folds a Death record with a living villager's looks into them.
        self.deaths.write_bytes(self.deaths.read_bytes().replace(b"Head: 1\r\n  Body: 1", b"Head: 5\r\n  Body: 6"))
        alike, _nameless, _bodies, _taken = nn.evidence(self.folder, 3, 1)
        self.assertEqual(alike, {("Soda", 5, 6): 2})

    def test_it_is_refused_while_the_game_runs_or_when_no_name_is_shared(self):
        before = self.save.read_bytes()
        with self.assertRaises(Exception):
            nn.number_names(self.folder, 3, 1, processes=Running(), now=NOW)
        self.assertEqual(self.save.read_bytes(), before)
        nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        with self.assertRaises(ln.LastNamesError):
            nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)


class TheWindows(unittest.TestCase):
    def test_a_page_starts_only_at_a_generation_the_tree_has(self):
        # Codex, #557: with generations 1 and 3 and nobody in 2, a break at 2 is no page.
        v = village(gen.Person(1, "Ann", 1, 1, alive=True, generation=1),
                    gen.Person(2, "Bob", 2, 2, alive=True, generation=3))
        self.assertEqual(ft.page_spans(ft.Edits(pages=[2]), v), [(1, 3)])
        self.assertEqual(ft.page_spans(ft.Edits(pages=[3]), v), [(1, 3), (3, 3)])

    def test_the_tree_maker_reports_a_running_game(self):
        tree = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        offer = tree[tree.index("    def _number_names(self)"):tree.index("    def _reset_frames(self)")]
        self.assertIn("except (vv_last_names.LastNamesError, vv_log_tools.LogToolError, vv_save_backup.BackupError,",
                      offer)
        self.assertIn("vv_number_names.evidence(self.folder, self.game, self.slot)", offer,
                      "the save's look-alikes count before \"No two villagers share a name\"")

    def test_only_the_current_villages_tree_files_are_rekeyed(self):
        source = (ROOT / "src" / "vv_last_names.py").read_text(encoding="utf-8")
        plan = source[source.index("def _plan_family_trees("):source.index("def _first_line(")]
        self.assertIn('and tribe and data.get("tribe") == tribe:', plan)

    def test_the_tree_maker_and_repair_logs_offer_it(self):
        tree = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        self.assertIn('ttk.Button(tab, text="Number duplicate names", command=self._number_names)', tree)
        self.assertIn('("Number Duplicate Names...", "", self._number_names)', tree)
        offer = tree[tree.index("    def _number_names(self)"):tree.index("    def _reset_frames(self)")]
        self.assertLess(offer.index("messagebox.askyesno("), offer.index("vv_number_names.number_names("),
                        "the save is edited only when the player says so")
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        checklist = gui[gui.index("    def _repair_checklist("):gui.index("    def _repair_questions(")]
        # Ticked only when the save's names do not follow the numbering rule (the owner, 2026-10-08:
        # "update ... the repair logs and save data and everything").
        self.assertIn("number_var = tk.BooleanVar(value=bool(misnumbered))", checklist)
        repair = gui[gui.index("    def _repair_logs("):gui.index("    def _repair_checklist(")]
        self.assertIn("lambda: vv_number_names.number_names(folder, number, info.slot, numbering)", repair)
        self.assertIn('number_order_var = tk.StringVar(value=vv_genealogy.NUMBER_ORDERS["appearance"])', checklist)
        self.assertIn("self.edits.number_order))", offer)
        self.assertLess(repair.index("vv_last_names.give_last_names("), repair.index("vv_number_names.number_names("),
                        "numbered after any last names are given")


if __name__ == "__main__":
    unittest.main()
