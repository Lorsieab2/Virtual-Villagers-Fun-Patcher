"""Records that contradict each other: Check Saves & Logs finds them, Repair Saves & Logs puts them right
(src/vv_log_contradictions.py), and the writers no longer make them (all five games).

The owner's A New Home log (2026-10-10): Cheop Bahati had a Birth record and a backfilled "Arrived 11";
Lulu Chuchip, the Golden Child, a Birth and a backfilled "Arrived 13"; Hoani Chuchip "Arrived 8" and a
backfilled "Arrived 12"; the Deaths log "Death 15" four times; the Repairs logs "Repair 1" in both the
older "Repairs" folder and "Repairs Made".  Every folder here is built in a temporary directory.
"""
from __future__ import annotations

import gzip
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_additions as additions  # noqa: E402
import vv_log_contradictions as contra  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
NOW = datetime(2026, 10, 10, 12, 0, 0)
FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
STEMS = {1: "Virtual Villagers", 2: "Virtual Villagers - The Lost Children", 3: "Virtual Villagers - The Secret City",
         4: "Virtual Villagers - The Tree of Life", 5: "Virtual Villagers - New Believers"}
VILLAGE = "Village: Kalahuna Tribe (Save 1)"


def birth(name: str, head: int, body: int, note: str = "") -> str:
    return (f"Birth\n  Child: {name}\n    Sex: Male\n    Head: {head}\n    Body: {body}\n    Likes: (none)\n"
            f"    Dislikes: (none)\n  Mother: Chapa Wanjiko\n    Head: 18\n    Body: 0\n  Father: Usutu Bahati\n"
            f"    Head: 18\n    Body: 1\n  Born as: Single birth\n" + (f"  Note: {note}\n" if note else "") + "\n")


def arrived(n: int, name: str, head: int, body: int, how: str = "unknown", backfill: bool = True,
            special: str = "") -> str:
    return (f"Arrived {n}\n  Name: {name}\n" + (f"  Special villager: {special}\n" if special else "")
            + f"  Age at arrival: (unknown)\n  Sex: Male\n  Head: {head}\n  Body: {body}\n  Likes: (none)\n"
            f"  Dislikes: (none)\n  How: {how}\n"
            + ("  Note: Recorded afterwards (arrived before this log existed)\n" if backfill else "") + "\n")


def death(n: int, name: str, head: int, body: int, age: int = 1600) -> str:
    return (f"Death {n}\n  Name: {name}\n  Age at death: {age}\n  Sex: Male\n  Cause of death: Old age\n"
            f"  Head: {head}\n  Body: {body}\n  Likes: (none)\n  Dislikes: (none)\n\n")


class Folder:
    def __init__(self, game: int = 1):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / f"{STEMS[game]} - Modded"
        self.path.mkdir()
        self.game = game

    def write(self, relative: str, text: str) -> Path:
        p = self.path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
        return p

    def births(self, text: str) -> Path:
        return self.write(f"{LOGS}\\Births and Conceptions\\Virtual Villagers {self.game} Births and Conceptions Log 1.txt",
                          VILLAGE + "\n" + text)

    def read(self, path: Path) -> str:
        return path.read_bytes().decode("latin-1").replace("\r\n", "\n")

    def repair(self, answers: dict | None = None) -> dict:
        kinds = [contra.plan(self.path, self.game, 1)]
        chosen_answers = {k: q.default for kind in kinds for k, q in kind.questions.items()}
        chosen_answers.update(answers or {})
        return additions.apply(self.path, kinds, {"contradictions"}, chosen_answers)


class BornAndArrivedTests(unittest.TestCase):
    def test_a_birth_and_a_backfilled_arrived_record_is_found_and_the_arrived_one_taken_out(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                f = Folder(game)
                path = f.births(birth("Cheop Bahati", 4, 15) + arrived(11, "Cheop Bahati", 4, 15, how="Founder"))
                found = contra.find(f.path, game, 1)
                self.assertEqual([x.kind for x in found], ["born_and_arrived"])
                self.assertTrue(found[0].wrong)
                self.assertIn("Cheop Bahati", found[0].text)
                done = f.repair()
                text = f.read(path)
                self.assertNotIn("Arrived 11", text)
                self.assertIn("  Child: Cheop Bahati", text)
                self.assertEqual(done["contradictions"][0].count, 1)
                copy = f.path / DATA / "Copies Made Before Repairs" / LOGS / "Births and Conceptions"
                kept = list(copy.glob("*" + tools.WORD_BACKUP_SUFFIX + "*"))
                self.assertEqual(len(kept), 1, "the record taken out is kept in the copy made before the repair")
                self.assertIn("Arrived 11", kept[0].read_bytes().decode("latin-1"))
                self.assertEqual(contra.find(f.path, game, 1), [], "a second check finds nothing")
                self.assertNotIn("\n\n\n", text, "no double blank line is left behind")

    def test_a_how_unknown_pair_is_left_to_plan_born_arrived(self):
        # The Golden Child Lulu: a Birth and a backfilled "How: unknown" Arrived record is the kind
        # fix/vv1-expected-father's plan_born_arrived (and the checker) handle: not reported twice.
        f = Folder(1)
        f.births(arrived(13, "Lulu Chuchip", 19, 19, special="Golden Child")
                 + birth("Lulu Chuchip", 19, 19, "Recorded afterwards (the Golden Child's parents)"))
        self.assertEqual(contra.find(f.path, 1, 1), [])
        # (plan_born_arrived offers it once who is alive can be read: here, nobody of that look.)
        self.assertEqual(len(additions.plan_backfilled_arrivals(f.path, 1, 1, {}, None).removes), 1)

    def test_arrived_twice_the_backfilled_unknown_one_is_taken_out(self):
        f = Folder(1)
        path = f.births(arrived(8, "Hoani Chuchip", 11, 2, how="Barrel of Babies")
                        + arrived(12, "Hoani Chuchip", 11, 2))
        found = contra.find(f.path, 1, 1)
        self.assertEqual(len(found), 1)
        self.assertIn("Arrived 12", found[0].text)
        f.repair()
        text = f.read(path)
        self.assertEqual(text.count("  Name: Hoani Chuchip"), 1)
        self.assertIn("How: Barrel of Babies", text)
        self.assertIn("Arrived 1\n", text, "the Arrived records are numbered on without a gap")

    def test_keep_both_answer_changes_nothing(self):
        f = Folder(1)
        path = f.births(birth("Cheop Bahati", 4, 15) + arrived(11, "Cheop Bahati", 4, 15, how="Founder"))
        before = path.read_bytes()
        key = next(iter(contra.plan(f.path, 1, 1).questions))
        f.repair({key: contra.KEEP})
        self.assertEqual(path.read_bytes(), before)

    def test_records_written_live_are_never_taken_out(self):
        # An Arrived record the game wrote as it happened (no backfill note) beside a Birth: no
        # backfill made it, so nothing says which is wrong -- left alone.
        f = Folder(1)
        f.births(birth("Kai", 3, 3) + arrived(1, "Kai", 3, 3, how="Custom Island Event", backfill=False))
        self.assertEqual([x for x in contra.find(f.path, 1, 1) if x.wrong], [])

    def test_a_dead_namesake_owns_one_record(self):
        # A villager of the same name and looks who died: two villagers, two records -- nothing found.
        f = Folder(1)
        f.births(birth("Kai", 3, 3) + arrived(2, "Kai", 3, 3))
        f.write(f"{LOGS}\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt",
                VILLAGE + "\n" + death(1, "Kai", 3, 3))
        self.assertEqual([x for x in contra.find(f.path, 1, 1) if x.kind == "born_and_arrived"], [])

    def test_a_look_change_is_followed(self):
        f = Folder(1)
        f.births(birth("Papu Alosaka", 16, 14)
                 + "Appearance changed\n  Name: Papu Alosaka\n  Old head: 16\n  Old body: 14\n  New head: 5\n"
                   "  New body: 14\n  Changed by: an island event\n\n"
                 + arrived(14, "Papu Alosaka", 5, 14))
        found = contra.find(f.path, 1, 1)
        self.assertEqual([x.kind for x in found], ["born_and_arrived"])


class PromptTests(unittest.TestCase):
    """The owner (2026-10-10): every contradiction is asked about -- a resolution or "Don't know /
    leave it" -- and "Retroactively edit records? yes/no"."""

    def make(self) -> tuple[Folder, Path, Path]:
        f = Folder(1)
        births = f.births(birth("Cheop Bahati", 4, 15) + arrived(11, "Cheop Bahati", 4, 15, how="Founder"))
        deaths = f.write(f"{LOGS}\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt",
                         VILLAGE + "\n" + death(15, "Hawa", 17, 5) + death(15, "Silko", 4, 14))
        return f, births, deaths

    def answers(self, f: Folder, resolution: str | None, retro: str) -> dict:
        kind = contra.plan(f.path, 1, 1)
        out = {}
        for key, q in kind.questions.items():
            out[key] = retro if key.startswith("retro|") else (resolution or q.options[0])
        return out

    def test_every_contradiction_has_both_questions_and_a_leave_it_answer(self):
        f, _b, _d = self.make()
        kind = contra.plan(f.path, 1, 1)
        resolutions = [q for k, q in kind.questions.items() if k.startswith("contradiction|")]
        retros = [q for k, q in kind.questions.items() if k.startswith("retro|")]
        self.assertEqual(len(resolutions), 2)
        self.assertEqual(len(retros), 2)
        for q in resolutions:
            self.assertIn(contra.LEAVE, q.options)
        for q in retros:
            self.assertEqual(q.options, [contra.RETRO_YES, contra.RETRO_NO])
        self.assertEqual(kind.decided, 0, "nothing is decided without the player")

    def test_yes_corrects_the_older_records(self):
        f, births, deaths = self.make()
        f.repair(self.answers(f, None, contra.RETRO_YES))
        self.assertNotIn("Arrived 11", f.read(births))
        self.assertIn("Death 16", f.read(deaths))

    def test_no_leaves_every_past_record_and_is_not_asked_again(self):
        f, births, deaths = self.make()
        before = (births.read_bytes(), deaths.read_bytes())
        answers = self.answers(f, None, contra.RETRO_NO)
        kinds = [contra.plan(f.path, 1, 1)]
        additions.apply(f.path, kinds, {"contradictions"}, answers)
        self.assertEqual((births.read_bytes(), deaths.read_bytes()), before)
        self.assertEqual(len(contra.remember(f.path, 1, 1, kinds, answers)), 2)
        self.assertEqual([x for x in contra.find(f.path, 1, 1) if x.wrong], [], "remembered: no longer WRONG")
        self.assertEqual(contra.plan(f.path, 1, 1).questions, {}, "...and not asked again")

    def test_leave_it_changes_nothing_and_asks_again(self):
        f, births, deaths = self.make()
        before = (births.read_bytes(), deaths.read_bytes())
        answers = self.answers(f, contra.LEAVE, contra.RETRO_YES)
        kinds = [contra.plan(f.path, 1, 1)]
        additions.apply(f.path, kinds, {"contradictions"}, answers)
        contra.remember(f.path, 1, 1, kinds, answers)
        self.assertEqual((births.read_bytes(), deaths.read_bytes()), before)
        self.assertEqual(len([x for x in contra.find(f.path, 1, 1) if x.wrong]), 2)


class NumberTests(unittest.TestCase):
    def test_a_death_number_used_again_is_numbered_after_the_highest(self):
        f = Folder(1)
        f.write(f"{LOGS}\\Deaths\\Virtual Villagers 1 Deaths Log 1.txt",
                VILLAGE + "\n" + death(13, "Yepa", 2, 8) + death(14, "Iruwa", 13, 19))
        new = f.write(f"{LOGS}\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt",
                      VILLAGE + "\n" + death(15, "Hawa", 17, 5) + death(15, "Silko", 4, 14)
                      + death(15, "Ponui", 9, 15) + death(15, "Kuruk", 12, 2))
        found = contra.find(f.path, 1, 1)
        self.assertEqual([x.kind for x in found], ["death_number"] * 3)
        f.repair()
        heads = [line for line in f.read(new).split("\n") if line.startswith("Death ")]
        self.assertEqual(heads, ["Death 15", "Death 16", "Death 17", "Death 18"])
        self.assertEqual(contra.find(f.path, 1, 1), [])

    def test_a_death_record_kept_in_both_folders_is_one_record(self):
        f = Folder(1)
        f.write(f"{LOGS}\\Deaths\\Virtual Villagers 1 Deaths Log 1.txt", VILLAGE + "\n" + death(1, "Yepa", 2, 8))
        f.write(f"{LOGS}\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt",
                VILLAGE + "\n" + death(1, "Yepa", 2, 8) + death(2, "Hawa", 17, 5))
        self.assertEqual(contra.find(f.path, 1, 1), [])

    def test_repair_numbers_in_both_repairs_folders(self):
        f = Folder(1)
        f.write(f"{LOGS}\\Repairs\\Virtual Villagers 1 Repairs Log 1.txt",
                VILLAGE + "\nRepair 1\n  Date: a\n\nRepair 2\n  Date: b\n\n")
        new = f.write(f"{LOGS}\\Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt",
                      VILLAGE + "\nRepair 1\n  Date: c\n\n")
        found = contra.find(f.path, 1, 1)
        self.assertEqual([x.kind for x in found], ["repair_number"])
        f.repair()
        self.assertIn("Repair 3\n", f.read(new))
        # The next Repairs record numbers on after both folders' (src/vv_log_tools.py note_word_repair).
        tools.note_word_repair(f.path, 1, VILLAGE, [tools.WordFix("x.txt", 1, "x.bak")], NOW)
        self.assertIn("Repair 4\n", f.read(new))
        self.assertEqual(contra.find(f.path, 1, 1), [])

    def test_note_word_repair_numbers_on_after_the_older_folder(self):
        # Before the fix: "Repair 1" again in Repairs Made beside the older folder's Repair 1-2.
        f = Folder(3)
        f.write(f"{LOGS}\\Repairs\\Virtual Villagers 3 Repairs Log 1.txt",
                VILLAGE + "\nRepair 1\n  Date: a\n\nRepair 2\n  Date: b\n\n")
        (f.path / LOGS / "Repairs Made").mkdir(parents=True)
        tools.note_word_repair(f.path, 3, VILLAGE, [tools.WordFix("x.txt", 1, "x.bak")], NOW)
        made = f.path / LOGS / "Repairs Made" / "Virtual Villagers 3 Repairs Log 1.txt"
        self.assertIn("Repair 3\n", f.read(made))


class BoundaryTests(unittest.TestCase):
    def test_the_like_and_dislike_words_boundary_moves_with_a_record_taken_out(self):
        f = Folder(1)
        path = f.births(birth("Cheop Bahati", 4, 15) + arrived(11, "Cheop Bahati", 4, 15, how="Founder") + birth("Ahi", 5, 5))
        data = path.read_bytes()
        boundary = data.index(b"Birth\r\n  Child: Ahi")       # the older words end before Ahi's record
        words = f.write(f"{DATA}\\Like and Dislike Words\\Virtual Villagers 1 Log Words.dat",
                        f"{boundary}\t{LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt\n")
        f.repair()
        after = path.read_bytes()
        checker = tools.load_checker()
        moved = checker.word_boundaries(f.path, 1)[
            f"{LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt".lower()]
        self.assertEqual(moved, after.index(b"Birth\r\n  Child: Ahi"),
                         "the boundary still stands before Ahi's record")
        self.assertIn(b"\t", words.read_bytes())


class GoldenTests(unittest.TestCase):
    def test_the_golden_childs_birth_takes_the_arrived_records_place(self):
        f = Folder(1)
        conception = ("Conception 1\n  Mother: Kaula Akikai\n    Age at conception: 600\n    Head: 12\n    Body: 6\n"
                      "  Father: Hoani Chuchip\n    Age at conception: 600\n    Head: 11\n    Body: 2\n"
                      "  Babies in pregnancy: 1\n\n")
        path = f.births(conception + arrived(13, "Lulu Chuchip", 19, 19, special="Golden Child"))
        kind = additions.plan_golden(f.path, 1, 1)
        key, question = next(iter(kind.questions.items()))
        answer = next(o for o in question.options if o != additions.DONT_KNOW)
        additions.apply(f.path, [kind], {"golden"}, {key: answer})
        text = f.read(path)
        self.assertNotIn("Arrived 13", text)
        self.assertIn("Birth\n  Child: Lulu Chuchip", text)
        self.assertIn("  Born as: Golden Child", text)
        self.assertEqual(contra.find(f.path, 1, 1), [])


class CheckerMirrorTests(unittest.TestCase):
    def test_names_related(self):
        checker = tools.load_checker()
        self.assertTrue(checker.names_related(2, "Cheop", "Cheop Bahati"))
        self.assertTrue(checker.names_related(2, "Kaula Bahati I", "Kaula Bahati"))
        self.assertTrue(checker.names_related(2, "Hoani Guedadosano", "Hoani Guedadosa"))   # cut at 15
        self.assertFalse(checker.names_related(2, "Hoani Guedadosano", "Hoani Gue"))        # not a cut
        self.assertFalse(checker.names_related(2, "Kaimi", "Kai"))
        self.assertFalse(checker.names_related(2, "Cheop", "Cheop"))

    def test_check_logs_reports_the_contradictions_as_wrong(self):
        f = Folder(1)
        f.path.joinpath(f"{STEMS[1]}1.ldw").write_bytes(
            gzip.decompress((FIXTURES / "vv1-huttest-1.ldw.gz").read_bytes()))
        header = sorted(additions.current_villages(f.path, 1, 1))[0]      # the save's own village
        f.write(f"{LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt",
                header + "\n" + birth("Cheop Bahati", 4, 15) + arrived(11, "Cheop Bahati", 4, 15, how="Founder"))
        result = tools.check_logs(f.path, 1, 1)
        self.assertIn("one villager recorded twice", result.text)
        self.assertGreaterEqual(result.wrong, 1)


if __name__ == "__main__":
    unittest.main()
