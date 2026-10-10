"""Names the game's Villager Details screen cut short (src/vv_cut_names.py).

The owner (2026-10-07): "Full names will be in the logs.  Any truncated in-game name will be matched
to the correct villager in the logs using as much data as possible.  Family trees will use the full
names from the logs, then the save data."  And: "the repair logs thing should repair cut-off names
from the last save/log".

These tests build a small The Secret City save and log folder by hand (Last Names' fixture): the save
holds "Hoani Guedado Akik" (18 characters, what the Details screen keeps), the logs written before
the cut hold "Hoani Guedado Akikai", the ones written after it the cut name.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cut_names as cn  # noqa: E402
import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_last_names_rename import NOW, TABLE, NoGame, Running, entry  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
CUT = "Hoani Guedado Akik"            # 18 characters: what the Details screen keeps
FULL = "Hoani Guedado Akikai"


def person(n: int, name: str, head: int, body: int, sex: str = "Male", likes: str = "ants",
           dislikes: str = "bees", parents: str = "") -> str:
    return (f"Villager {n}\n  Name: {name}\n  Age: 400\n  Sex: {sex}\n  Head: {head}\n  Body: {body}\n"
            f"  Likes: {likes}\n  Dislikes: {dislikes}\n{parents}\n")


def father(name: str) -> str:
    return (f"  Parents:\n    Father: {name}\n      Head: 5\n      Body: 6\n"
            "    Mother: Aipi\n      Head: 7\n      Body: 8\n")


class CutNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        # The made-up save holds no tribe name: say which village is this one.
        named = mock.patch("vv_log_additions.current_villages", return_value={"Village: Tribe (Save 1)"})
        named.start()
        self.addCleanup(named.stop)
        self.save = self.folder / "Virtual Villagers - The Secret City1.ldw"
        self.write_save(entry(CUT, 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8),
                        entry("Kid", 0, 50, 9, 9, father=(CUT, 5, 6), mother=("Aipi", 7, 8)))
        self.before = (f"=== Virtual Villagers 3 -- 2026-10-01 ===\nVillage: Tribe (Save 1)\n"
                       + person(1, FULL, 5, 6) + person(2, "Aipi", 7, 8, "Female")
                       + person(3, "Kid", 9, 9, parents=father(FULL)))
        self.after = (f"=== Virtual Villagers 3 -- 2026-10-03 ===\nVillage: Tribe (Save 1)\n"
                      + person(1, CUT, 5, 6) + person(2, "Aipi", 7, 8, "Female")
                      + person(3, "Kid", 9, 9, parents=father(CUT)))
        self.history = self.log("Tribe History/Village History 1.txt", self.before + self.after)
        self.births = self.log("Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt",
                               "Village: Tribe (Save 1)\n"
                               f"Birth\n  Child: Kid\n    Head: 9\n    Body: 9\n  Mother: Aipi\n    Head: 7\n"
                               f"    Body: 8\n  Father: {FULL}\n    Head: 5\n    Body: 6\n\n")

    def write_save(self, *people: bytes) -> None:
        self.save.write_bytes(b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))

    def log(self, relative: str, text: str) -> Path:
        path = self.folder / LOGS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode())
        return path

    def found(self):
        cuts, notes = cn.find_cut(self.folder, 3, 1)
        return {c.villager.name: c.full for c in cuts}, notes

    # ---- matching ---------------------------------------------------------

    def test_the_cut_name_is_matched_to_the_full_name_the_logs_keep(self):
        self.assertEqual(cn.DETAILS_ROOM, {1: 10, 2: 18, 3: 18, 4: 18, 5: 18})
        self.assertEqual(self.found(), ({CUT: FULL}, []))

    def test_another_sex_is_not_them(self):
        self.history.write_bytes(self.history.read_bytes().replace(
            f"  Name: {FULL}\r\n  Age: 400\r\n  Sex: Male".encode(), f"  Name: {FULL}\r\n  Age: 400\r\n  Sex: Female".encode()))
        self.assertEqual(self.found(), ({}, []))

    def test_a_dead_villager_is_not_them(self):
        self.log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                 f"Village: Tribe (Save 1)\nDeath 1\n  Name: {FULL}\n  Age at death: 1400\n  Head: 5\n  Body: 6\n\n")
        self.assertEqual(self.found(), ({}, []))

    def test_other_likes_are_not_them(self):
        self.history.write_bytes(self.history.read_bytes().replace(
            f"  Name: {FULL}\r\n  Age: 400\r\n  Sex: Male\r\n  Head: 5\r\n  Body: 6\r\n  Likes: ants".encode(),
            f"  Name: {FULL}\r\n  Age: 400\r\n  Sex: Male\r\n  Head: 5\r\n  Body: 6\r\n  Likes: crowds".encode()))
        self.assertEqual(self.found(), ({}, []))

    def test_other_looks_are_not_them(self):
        self.history.write_bytes(self.history.read_bytes().replace(
            f"  Name: {FULL}\r\n  Age: 400\r\n  Sex: Male\r\n  Head: 5".encode(),
            f"  Name: {FULL}\r\n  Age: 400\r\n  Sex: Male\r\n  Head: 4".encode()))
        self.assertEqual(self.found(), ({}, []))

    def test_two_candidates_decide_nothing_and_are_named(self):
        self.log("Tribe Population/Village Population 1.txt",
                 "Village: Tribe (Save 1)\n" + person(1, CUT + "oa", 5, 6))
        found, notes = self.found()
        self.assertEqual(found, {})
        self.assertEqual(len(notes), 1)
        self.assertIn(f"could be {FULL} or {CUT}oa", notes[0])

    def test_a_name_the_player_shortened_on_purpose_is_never_restored(self):
        # Review, 2026-10-07: "Chapa Wanjiko" renamed "Chapa" in the game -- far shorter than the box
        # keeps, and the full name fits the box, so the screen never cut it.
        self.write_save(entry("Chapa", 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8))
        self.log("Tribe Population/Village Population 1.txt",
                 "Village: Tribe (Save 1)\n" + person(1, "Chapa Wanjiko", 5, 6))
        self.assertEqual(self.found(), ({}, []))
        # A save name the box's length but a full name that would have fitted is not a cut either.
        self.write_save(entry("Chapa Wanjiko Kaul", 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8))
        self.log("Tribe Population/Village Population 1.txt",
                 "Village: Tribe (Save 1)\n" + person(1, "Chapa Wanjiko Kaul", 5, 6))
        self.assertEqual(self.found(), ({}, []))

    def test_a_wide_name_cut_short_of_the_limit_is_restored(self):
        # Codex, #566: wide letters leave 15 of an 18 limit, and the full name may be only 16.
        wide, wide_full = "MMMMM MMMMM MMMM", "MMMMM MMMMM MMMMM"
        self.write_save(entry(wide[:15], 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8))
        self.log("Tribe Population/Village Population 1.txt",
                 "Village: Tribe (Save 1)\n" + person(1, wide_full[:16], 5, 6))
        found, _notes = self.found()
        self.assertEqual(found, {wide[:15]: wide_full[:16]})

    def test_a_villager_brought_back_after_death_is_still_them(self):
        # Codex, #566: a Death record, then a living snapshot at or past that age (New Believers'
        # Reanimate, a Custom Island Event's revived skeleton) -- alive again.
        self.log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                 f"Village: Tribe (Save 1)\nDeath 1\n  Name: {FULL}\n  Age at death: 380\n  Head: 5\n  Body: 6\n\n")
        self.assertEqual(self.found(), ({CUT: FULL}, []))       # snapshots list them at age 400
        # Never seen alive after that age: gone.
        self.history.write_bytes(self.history.read_bytes().replace(b"Age: 400", b"Age: 300"))
        self.assertEqual(self.found(), ({}, []))

    def test_brought_back_shows_under_the_cut_name_too(self):
        # Codex, #566: last logged in full at 300, died at 380, brought back -- the later snapshots
        # (age 400) carry the cut name.
        self.history.write_bytes(self.history.read_bytes().replace(
            f"  Name: {FULL}\r\n  Age: 400".encode(), f"  Name: {FULL}\r\n  Age: 300".encode()))
        self.log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                 f"Village: Tribe (Save 1)\nDeath 1\n  Name: {FULL}\n  Age at death: 380\n  Head: 5\n  Body: 6\n\n")
        self.assertEqual(self.found(), ({CUT: FULL}, []))

    def test_an_unaccounted_newcomer_is_not_gone(self):
        # Codex, #566: the same heading names a living newcomer; only "Left the village ..." is gone.
        self.log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                 f"Village: Tribe (Save 1)\nUnaccounted 1\n  Name: {FULL}\n"
                 "  What: Arrived with no Birth record or known arrival\n  Head: 5\n  Body: 6\n\n")
        self.assertEqual(self.found(), ({CUT: FULL}, []))
        self.log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                 f"Village: Tribe (Save 1)\nUnaccounted 1\n  Name: {FULL}\n"
                 "  What: Left the village with no Death or Disappeared record\n  Head: 5\n  Body: 6\n\n")
        self.assertEqual(self.found(), ({}, []))

    def test_a_death_record_under_the_cut_name_is_restored_for_one_brought_back(self):
        # Codex, #566: cut, died, brought back -- the Death record carries the cut name and is theirs.
        deaths = self.log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                          f"Village: Tribe (Save 1)\nDeath 1\n  Name: {CUT}\n  Age at death: 390\n  Head: 5\n"
                          "  Body: 6\n\n")
        work = cn.plan(self.folder, 3, 1)
        changed = {c.path: c.updated for c in work.changes}
        self.assertIn(deaths, changed)
        self.assertIn(f"  Name: {FULL}\r\n".encode(), changed[deaths])

    def test_an_accented_name_is_restored(self):
        # Codex, #566: the games' text box takes Latin-1 letters.
        # A game-named villager first, as the game's own name list puts there (the table is found by them).
        self.write_save(entry("Aipi", 1, 50, 7, 8), entry("Kid", 0, 50, 9, 9), entry("Élodie Guedado Aki", 0, 1, 5, 6))
        path = self.log("Tribe Population/Village Population 1.txt", "")
        # The games write their logs in Latin-1, as the patcher reads them.
        path.write_bytes(("Village: Tribe (Save 1)\n" + person(1, "Élodie Guedado Akikai", 5, 6))
                         .replace("\n", "\r\n").encode("latin-1"))
        self.assertEqual(self.found()[0], {"Élodie Guedado Aki": "Élodie Guedado Akikai"})

    def test_a_name_longer_than_the_screen_keeps_was_never_cut(self):
        self.write_save(entry(FULL[:19], 0, 1, 5, 6), entry("Aipi", 1, 50, 7, 8))
        self.assertEqual(self.found(), ({}, []))

    def test_a_full_name_a_living_villager_has_is_theirs(self):
        self.write_save(entry(CUT, 0, 1, 5, 6), entry(FULL, 0, 2, 3, 3))
        self.assertEqual(self.found(), ({}, []))

    def test_two_living_villagers_with_the_cut_name_and_looks_cannot_be_told_apart(self):
        self.write_save(entry(CUT, 0, 1, 5, 6), entry(CUT, 0, 1, 5, 6))
        found, notes = self.found()
        self.assertEqual(found, {})
        self.assertEqual(len(notes), 1)
        self.assertIn(f"2 living villagers are called {CUT}", notes[0])

    def test_without_the_tribe_name_nothing_is_matched(self):
        with mock.patch("vv_log_additions.current_villages", return_value=None):
            found, notes = self.found()
        self.assertEqual(found, {})
        self.assertIn("tribe name could not be read", notes[0])

    # ---- restoring --------------------------------------------------------

    def test_the_plan_renames_the_save_and_every_record_of_the_cut_name(self):
        work = cn.plan(self.folder, 3, 1)
        self.assertEqual(work.renames, {(CUT, 5, 6): FULL})
        self.assertEqual({c.path for c in work.changes}, {self.save, self.history})

    def test_restore_renames_the_save_and_the_logs_after_a_backup(self):
        result = cn.restore(self.folder, 3, 1, NoGame(), NOW)
        self.assertEqual([v.name for v in ln.living(self.folder, 3, 1)], [FULL, "Aipi", "Kid"])
        kid = TABLE + 2 * 0x11C + 0x14
        self.assertEqual(self.save.read_bytes()[kid + 0x24:kid + 0x24 + len(FULL) + 1], FULL.encode() + b"\0",
                         "the child's father field")
        text = self.history.read_bytes().decode()
        self.assertNotIn(f"{CUT}\r\n", text)
        self.assertEqual(text.count(f"Name: {FULL}\r\n"), 2)
        self.assertEqual(text.count(f"Father: {FULL}\r\n"), 2)
        backup = Path(result.backup.backup_folder)
        self.assertIn(cn.BACKUP_LABEL, backup.name)
        self.assertIn(CUT.encode() + b"\0", (backup / self.save.name).read_bytes())
        self.assertEqual(cn.find_cut(self.folder, 3, 1), ([], []), "nothing is left to restore")

    def test_restore_is_refused_while_the_game_runs_or_with_nothing_to_restore(self):
        before = self.save.read_bytes()
        with self.assertRaises(tools.LogToolError):
            cn.restore(self.folder, 3, 1, Running(), NOW)
        self.assertEqual(self.save.read_bytes(), before)
        self.history.write_bytes(self.after.replace("\n", "\r\n").encode())
        self.births.unlink()
        with self.assertRaises(ln.LastNamesError):
            cn.restore(self.folder, 3, 1, NoGame(), NOW)
        self.assertFalse((self.folder / "Backups").exists())

    # ---- Check Saves & Logs -----------------------------------------------

    def test_check_saves_and_logs_notes_the_cut_names(self):
        checker = tools.load_checker()
        with mock.patch.object(checker, "check", return_value=checker.Report()), \
                mock.patch("vv_log_additions.plan", return_value=[]), \
                mock.patch("vv_last_names.wrong_last_names", return_value=("mother", [])):
            text = tools.check_logs(self.folder, 1, 3).text
        self.assertIn(f"1 name(s) the game's Villager Details screen cut short: {CUT} ({FULL}); "
                      "Repair Saves & Logs restores them.", text)

    # ---- the family tree --------------------------------------------------

    def test_the_family_tree_shows_the_full_name_as_one_villager(self):
        village = gen.load_village(self.folder, 3, 1)
        names = sorted(p.name for p in village.known())
        self.assertEqual(names, sorted(["Aipi", FULL, "Kid"]))
        dad = next(p for p in village.known() if p.name == FULL)
        kid = next(p for p in village.known() if p.name == "Kid")
        self.assertTrue(dad.alive)
        self.assertEqual(kid.father, dad.id)
        self.assertEqual(village.full_names, {(CUT, 5, 6): FULL})
        # Last Names and Number Duplicate Names rename the records as written: they see the cut name.
        plain = gen.load_village(self.folder, 3, 1, full_names=False)
        self.assertIn(CUT, {p.name for p in plain.living()})

    def test_tree_edits_made_under_the_cut_name_follow_the_full_name(self):
        village = gen.load_village(self.folder, 3, 1)
        edits = ft.Edits.from_data({"format": 1, "entries": {f"{CUT}|5|6": {"hidden": True}}})
        moved = ft.full_name_edits(edits, village)
        self.assertEqual(moved.entries, {f"{FULL}|5|6": {"hidden": True}})
        plain = gen.load_village(self.folder, 3, 1, full_names=False)
        self.assertIs(ft.full_name_edits(edits, plain), edits)


class MergedTreeEdits(unittest.TestCase):
    def test_a_repeated_key_merges_without_breaking_moves(self):
        # Review, 2026-10-07: two [dx, dy] moves must not join into a three-number list.
        import json
        import vv_family_tree as ft
        text = '{"moved": {"A|1|1": [5, 6], "A|1|1": [7, 8]}, "lines": {"k": ["a"], "k": ["b", "a"]}, ' \
               '"entries": {"A|1|1": {"colour": "red"}, "A|1|1": {"colour": "blue", "bold": true}}}'
        merged = json.loads(text, object_pairs_hook=ft._merge_pairs)
        self.assertEqual(merged["moved"]["A|1|1"], [5, 6])
        self.assertEqual(merged["lines"]["k"], ["a", "b"])
        self.assertEqual(merged["entries"]["A|1|1"], {"colour": "red", "bold": True})


class RepairWiring(unittest.TestCase):
    """Repair Saves & Logs: restoring the cut names is ticked by default, runs before the last names and
    the numbering, and holds them off while it is ticked."""
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def body(self, start: str, end: str) -> str:
        return self.SOURCE[self.SOURCE.index(start):self.SOURCE.index(end)]

    def test_the_survey_finds_them_and_the_checklist_offers_them_ticked(self):
        repair = self.body("    def _repair_logs(", "    def _repair_checklist(")
        self.assertIn("cuts = vv_cut_names.find_cut(folder, number, info.slot)", repair)
        self.assertIn("rearm, chosen, answers, names, numbering, restore_cuts, to_pause, speed_choice = picked", repair)
        checklist = self.body("    def _repair_checklist(", "    def _last_names_dialog(")
        self.assertIn("cuts_var = tk.BooleanVar(value=bool(cuts))", checklist)
        self.assertIn('text=f"Restore {len(cuts)} name(s) the Villager Details screen cut short "', checklist)
        self.assertIn("after the cut names are restored: Repair, then", checklist)
        self.assertIn("names if names_var.get() and (names[\"chosen\"] or names.get(\"rules_changed\")\n"
                      "                                                               or names.get(\"arrivals_changed\"))\n"
                      "                                 and not restore else None", checklist)
        self.assertIn("if number_var.get() and not restore else None", checklist)
        for widget in ("names_tick", "names_choose", "number_tick"):
            self.assertIn(widget, checklist.split("def cut_first", 1)[1])

    def test_they_are_restored_before_the_last_names_and_the_numbering(self):
        repair = self.body("    def _repair_logs(", "    def _repair_checklist(")
        restore = repair.index("vv_cut_names.restore(folder, number, info.slot)")
        self.assertLess(repair.index("vv_log_tools.approve_repair("), restore)
        self.assertLess(restore, repair.index("vv_last_names.give_last_names("))
        self.assertLess(restore, repair.index("vv_number_names.number_names("))
        self.assertIn("Names the Villager Details screen cut short restored:", repair)


if __name__ == "__main__":
    unittest.main()
