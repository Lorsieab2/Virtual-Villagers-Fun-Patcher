"""Repair Saves & Logs: Remove false Unaccounted records (v1.35.80, all five games).

The owner's Kalahuna Tribe 2 (The Lost Children, Save 1): at 2026-10-20 09:22:01 the Unaccounted
Villagers reconciliation matched villagers by record number after the Elder Totems companion moved the
totems out of the table, and wrote 112 "Arrived" and 108 "Left" records of villagers who had only
moved (native/vvfp_cause_of_death/cod_roster.inc now follows identities).  Those records are taken out
only when the logs contradict them by identity, only on the player's word, the file copied first and the
removal listed in the Repairs log; a TRUE record -- one nothing contradicts -- always survives.

Also here: a backfilled "How: unknown" Arrived record of a villager renamed in the game ("Name changed")
whose record under the old name is in the log is offered as the duplicate it is.

Fixtures are built here; no file outside the repository is read.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_additions as additions  # noqa: E402
import vv_log_contradictions as contradictions  # noqa: E402
import vv_log_tools as tools  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
VILLAGE = "Village: Kalahuna Tribe 2 (Save 1)"
FOUND = "2026-10-20 09:22:01"


def unacc(n: int, name: str, what: str, age: int, sex: str, head: int, body: int, found: str = FOUND,
          last_seen: str = "2026-10-19 23:50:37") -> str:
    left = what == "Left"
    return (f"Unaccounted {n}\n  Name: {name}\n"
            f"  What: {'Left the village with no Death or Disappeared record' if left else 'Arrived with no Birth record or known arrival'}\n"
            f"  Age: {age}\n  Sex: {sex}\n  Health: 100\n  Head: {head}\n  Body: {body}\n  Likes: (none)\n"
            f"  Dislikes: (none)\n  Record: {n + 10}\n  Last seen: {last_seen if left else '(never before)'}\n"
            f"  Found: {found}\n\n")


def villager(n: int, name: str, age: int, sex: str, head: int, body: int) -> str:
    return f"Villager {n}\n  Name: {name}\n  Age: {age}\n  Sex: {sex}\n  Head: {head}\n  Body: {body}\n\n"


UNACCOUNTED = (VILLAGE + "\n"
               + unacc(1, "Mover", "Left", 300, "Male", 1, 1)          # moved: Arrived 2 is the same villager
               + unacc(2, "Mover", "Arrived", 301, "Male", 1, 1)
               + unacc(3, "Stayer", "Left", 400, "Female", 2, 2)       # in the snapshot of that save
               + unacc(4, "Dead One", "Left", 500, "Male", 3, 3)       # a Death record
               + unacc(5, "Old Timer", "Arrived", 900, "Female", 4, 4)  # in the snapshot before
               + unacc(6, "Born Here", "Arrived", 60, "Male", 5, 5)    # a Birth record
               + unacc(7, "Truly Gone", "Left", 350, "Female", 6, 6)   # TRUE: nothing says where she went
               + unacc(8, "Stranger", "Arrived", 700, "Male", 7, 7)    # TRUE: nobody knew him before
               + unacc(9, "Mover", "Left", 300, "Male", 1, 1, found="2026-10-18 23:38:44",
                       last_seen="2026-10-18 23:24:20"))               # TRUE: another check, no Arrived of his
HISTORY = ("=== Virtual Villagers 2 -- 2026-10-19 23:50:37 ===\n" + VILLAGE + "\n\n"
           + villager(1, "Old Timer", 899, "Female", 4, 4) + villager(2, "Stayer", 399, "Female", 2, 2) + "\n"
           + "=== Virtual Villagers 2 -- 2026-10-20 09:22:01 ===\n" + VILLAGE + "\n\n"
           + villager(1, "Old Timer", 900, "Female", 4, 4) + villager(2, "Stayer", 400, "Female", 2, 2)
           + villager(3, "Mover", 301, "Male", 1, 1) + "\n")
DEATHS = (VILLAGE + "\nDeath 1\n  Name: Dead One\n  Age at death: 510\n  Sex: Male\n  Cause of death: Old age\n"
          "  Grave: Master Farmer\n  Epitaph: (none)\n  Head: 3\n  Body: 3\n\n")
BIRTHS = (VILLAGE + "\nBirth 1\n  Child: Born Here\n    Sex: Male\n    Head: 5\n    Body: 5\n    Likes: (none)\n"
          "    Dislikes: (none)\n  Mother: Ma\n    Head: 9\n    Body: 9\n  Father: Pa\n    Head: 8\n    Body: 8\n\n"
          "Arrived 1\n  Name: Lupa Tangaroa\n  Age at arrival: 300\n  Sex: Female\n  Head: 24\n  Body: 28\n"
          "  Likes: (none)\n  Dislikes: (none)\n  How: Founder\n\n"
          "Name changed\n  Name: Coral Tangaroa\n  Old name: Lupa Tangaroa\n  Age: 300\n  Head: 24\n  Body: 28\n"
          "  Likes: (none)\n  Dislikes: (none)\n\n"
          "Arrived 2\n  Name: Coral Tangaroa\n  Age at arrival: (unknown)\n  Age when recorded: 310\n  Sex: Female\n"
          "  Head: 24\n  Body: 28\n  Likes: (none)\n  Dislikes: (none)\n  How: unknown\n"
          "  Note: Recorded afterwards (arrived before this log existed)\n\n"
          "Arrived 3\n  Name: Lone Backfill\n  Age at arrival: (unknown)\n  Age when recorded: 310\n  Sex: Female\n"
          "  Head: 25\n  Body: 25\n  Likes: (none)\n  Dislikes: (none)\n  How: unknown\n"
          "  Note: Recorded afterwards (arrived before this log existed)\n\n")


class NoGame:
    def find(self, exe):
        return []


def make(folder: Path, game: int, unaccounted: str = UNACCOUNTED, history: str = HISTORY,
         births: str = BIRTHS) -> Path:
    files = {
        f"Unaccounted Villagers/Virtual Villagers {game} Unaccounted Villagers Log 1.txt": unaccounted,
        "Tribe History/Village History 1.txt": history.replace("Virtual Villagers 2 --", f"Virtual Villagers {game} --"),
        f"Deaths and Disappearances/Virtual Villagers {game} Deaths Log 1.txt": DEATHS,
        f"Births and Conceptions/Virtual Villagers {game} Births and Conceptions Log 1.txt": births,
    }
    for rel, text in files.items():
        path = folder / LOGS / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
    return folder / LOGS / f"Unaccounted Villagers/Virtual Villagers {game} Unaccounted Villagers Log 1.txt"


def headings(path: Path) -> list[str]:
    return re.findall(r"^Unaccounted \d+", path.read_bytes().decode("latin-1"), re.M)


class FalseUnaccountedEveryGame(unittest.TestCase):
    def test_only_the_contradicted_records_are_offered(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                folder = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="vvf")))
                make(folder, game)
                verdicts = {(v.block.heading): v for v in contradictions.false_unaccounted(folder, game, 1)}
                false = sorted(h for h, v in verdicts.items() if v.false)
                self.assertEqual(false, [f"Unaccounted {n}" for n in (1, 2, 3, 4, 5, 6)])
                self.assertIn("moved to another record", verdicts["Unaccounted 1"].reason)
                self.assertIn("still in the village", verdicts["Unaccounted 3"].reason)
                self.assertIn("Death", verdicts["Unaccounted 4"].reason)
                self.assertIn("already in the village", verdicts["Unaccounted 5"].reason)
                self.assertIn("Birth", verdicts["Unaccounted 6"].reason)
                for kept in ("Unaccounted 7", "Unaccounted 8", "Unaccounted 9"):
                    self.assertFalse(verdicts[kept].false, kept)

    def test_true_records_survive_the_repair_and_it_is_recorded(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                folder = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="vvf")))
                log = make(folder, game)
                kind = contradictions.plan_false_unaccounted(folder, game, 1)
                self.assertEqual(len(kind.removes), 6)
                self.assertEqual(len(kind.notes), 3, kind.notes)
                self.assertTrue(all("is kept" in n for n in kind.notes))
                self.assertEqual(len(kind.questions), 1)
                question = next(iter(kind.questions.values()))
                for name in ("Mover", "Stayer", "Dead One", "Old Timer", "Born Here"):
                    self.assertIn(name, question.text)
                # "Keep them" changes nothing.
                before = log.read_bytes()
                additions.apply(folder, [kind], {kind.id}, {question.key: contradictions.FALSE_KEEP})
                self.assertEqual(log.read_bytes(), before)
                # Removed: only the false ones; a copy first; the Repairs log lists it.
                result = tools.approve_repair(folder, game, 1, NoGame(), chosen={kind.id},
                                              answers={question.key: contradictions.FALSE_REMOVE},
                                              kinds=[kind], rearm=False)
                self.assertEqual(headings(log), ["Unaccounted 7", "Unaccounted 8", "Unaccounted 9"])
                text = log.read_bytes().decode("latin-1")
                self.assertTrue(text.startswith(VILLAGE + "\r\n"))
                self.assertIn("  Name: Truly Gone\r\n", text)
                self.assertIn("  Name: Stranger\r\n", text)
                self.assertNotIn("\r\n\r\n\r\n", text)
                fixes = result.added["false_unaccounted"]
                self.assertEqual(fixes[0].count, 6)
                self.assertTrue(any(p.name.startswith(log.name + ".before-")
                                    for p in folder.rglob("*") if p.is_file()), "a copy made before")
                repairs = "".join(p.read_bytes().decode("latin-1") for p in folder.rglob("*Repairs Log*.txt"))
                self.assertIn(additions.ADDED["false_unaccounted"], repairs)
                self.assertFalse(contradictions.plan_false_unaccounted(folder, game, 1).removes, "nothing more")

    def test_the_check_reports_them_and_the_note_names_the_repair(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="vvf")))
        make(folder, 2)
        notes = [f.text for f in contradictions._notes(folder, 2, 1)]
        self.assertIn("Dead One is Unaccounted (left the village) and has a Death record (false: Repair Saves & "
                      "Logs, Remove false Unaccounted records, takes it out)", notes)

    def verdicts(self, game: int, **files) -> dict:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="vvf")))
        make(folder, game, **files)
        return {v.block.heading: v for v in contradictions.false_unaccounted(folder, game, 1)}

    def test_two_villagers_of_one_name_and_looks_are_never_paired_by_guess(self):
        # Codex, #600: a real departure and a different real arrival of the same name, sex, looks and
        # likes in one check (numbering off) are kept, never both called a move.
        found = "2026-10-20 10:00:00"
        log = (VILLAGE + "\n" + unacc(1, "Pair", "Left", 200, "Male", 8, 8, found=found)
               + unacc(2, "Pair", "Arrived", 201, "Male", 8, 8, found=found)
               + unacc(3, "Twin", "Left", 300, "Female", 9, 9, found=found)
               + unacc(4, "Twin", "Arrived", 500, "Female", 9, 9, found=found))
        history = ("=== Virtual Villagers 2 -- 2026-10-20 10:00:00 ===\n" + VILLAGE + "\n\n"
                   + villager(1, "Pair", 201, "Male", 8, 8) + villager(2, "Twin", 500, "Female", 9, 9) + "\n")
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = self.verdicts(game, unaccounted=log, history=history)
                self.assertTrue(v["Unaccounted 1"].false and v["Unaccounted 2"].false, "the move beyond doubt")
                self.assertFalse(v["Unaccounted 3"].false, v["Unaccounted 3"].reason)
                self.assertFalse(v["Unaccounted 4"].false, v["Unaccounted 4"].reason)
                self.assertIn("can not be told", v["Unaccounted 3"].reason)

    def test_a_birth_of_the_other_sex_or_two_that_fit_settle_nothing(self):
        # Codex, #600: the Birth must be this villager's -- the same sex too -- and the only one that fits.
        log = (VILLAGE + "\n" + unacc(1, "Born Here", "Arrived", 60, "Female", 5, 5)
               + unacc(2, "Two Fit", "Arrived", 60, "Male", 6, 6))
        birth = ("Birth {n}\n  Child: {name}\n    Sex: {sex}\n    Head: {h}\n    Body: {h}\n    Likes: (none)\n"
                 "    Dislikes: (none)\n  Mother: Ma\n    Head: 9\n    Body: 9\n  Father: Pa\n    Head: 8\n"
                 "    Body: 8\n\n")
        births = (VILLAGE + "\n" + birth.format(n=1, name="Born Here", sex="Male", h=5)
                  + birth.format(n=2, name="Two Fit", sex="Male", h=6) + birth.format(n=3, name="Two Fit", sex="Male", h=6))
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = self.verdicts(game, unaccounted=log, history="", births=births)
                self.assertFalse(v["Unaccounted 1"].false, "a Birth of the other sex is not hers")
                self.assertFalse(v["Unaccounted 2"].false, "two Births fit: neither is taken")
                self.assertIn("2 Birth / Arrived records fit", v["Unaccounted 2"].reason)

    def test_age_0_is_an_age(self):
        # Codex, #600 (the owner: 0 is a valid age): a newborn "Left" at age 0, in the next snapshot at 0.
        log = VILLAGE + "\n" + unacc(1, "Baby", "Left", 0, "Male", 0, 0)
        history = ("=== Virtual Villagers 2 -- 2026-10-20 09:22:01 ===\n" + VILLAGE + "\n\n"
                   + villager(1, "Baby", 0, "Male", 0, 0) + "\n")
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v = self.verdicts(game, unaccounted=log, history=history)
                self.assertTrue(v["Unaccounted 1"].false, v["Unaccounted 1"].reason)
                self.assertIn("still in the village", v["Unaccounted 1"].reason)

    def test_a_renamed_villagers_backfilled_arrival_is_offered(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                folder = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="vvf")))
                make(folder, game)
                kind = additions.plan_backfilled_arrivals(folder, game, 1, {("Coral Tangaroa", 24, 28): 1,
                                                                            ("Lone Backfill", 25, 25): 1}, None)
                offered = [q.text for q in kind.questions.values() if not q.key.endswith("|retro")]
                self.assertEqual(len(offered), 1, offered)
                self.assertIn("Coral Tangaroa", offered[0])
                self.assertIn("Arrived 1", offered[0])


if __name__ == "__main__":
    unittest.main()
