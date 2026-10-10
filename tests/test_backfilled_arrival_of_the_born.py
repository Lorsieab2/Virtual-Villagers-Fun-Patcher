"""A backfilled "How: unknown" Arrived record never outweighs a Birth record.

The owner's A New Home log holds, for Cheop Bahati, a Birth record AND "Arrived 11 ... How: unknown /
Note: Recorded afterwards (arrived before this log existed)": the arrival backfill wrote it when his
Birth record still named him "Cheop" (before Last Names gave him "Bahati"), so it saw no record of
him.  The Golden Child Lulu has the same pair (her Birth was added later).  So:

* the Family Tree Maker, the Matchmaker and the last-names window treat a villager with a Birth
  record as born, whatever such an Arrived record says -- a real arrival (a known "How") still counts;
* Check Logs reports the pair as WRONG, and Repair Saves & Logs offers to remove the Arrived record
  (asked first, the file copied before, a Repairs Made entry, the later "Arrived <n>" renumbered so
  the game's running count stays whole, and the file's Like and Dislike Words boundary moved);
* the arrival backfill itself matches a record named by the first name alone
  (native/parentage_export/arrival_backfill.inc; tests/test_arrived_records.py runs it).

Fixtures are built here; no file outside the repository is read.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy as gen  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_vv1_expected_father import vv1_save  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"

# name, male, family, head, body, carrying
VILLAGERS = [
    ("Usutu Bahati", True, 30, 7, 2, False),
    ("Chapa Wanjiko", False, 17, 18, 9, False),
    ("Cheop Bahati", True, 30, 4, 15, False),
    ("Silko Akikai", True, 44, 22, 5, False),
]

LOG = """Village: Kalahuna Tribe 1 (Save 1)
Birth
  Child: Cheop Bahati
    Sex: Male
    Head: 4
    Body: 15
    Likes: (none)
    Dislikes: (none)
  Mother: Chapa Wanjiko
    Head: 18
    Body: 9
  Father: Usutu Bahati
    Head: 7
    Body: 2

Arrived 1
  Name: Silko Akikai
  Age at arrival: 341
  Sex: Male
  Head: 22
  Body: 5
  Likes: (none)
  Dislikes: (none)
  How: Custom Island Event

Arrived 2
  Name: Cheop Bahati
  Age at arrival: (unknown)
  Age when recorded: 901
  Sex: Male
  Head: 4
  Body: 15
  Likes: (none)
  Dislikes: (none)
  How: unknown
  Note: Recorded afterwards (arrived before this log existed)

Arrived 3
  Name: Silko Akikai
  Age at arrival: (unknown)
  Sex: Male
  Head: 22
  Body: 5
  How: unknown
  Note: Recorded afterwards (arrived before this log existed)

"""


class BackfilledArrivalTests(unittest.TestCase):
    def build(self) -> Path:
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - A New Home"
        (game / LOGS / "Births and Conceptions").mkdir(parents=True)
        (game / DATA).mkdir(parents=True)
        (game / "Virtual Villagers1.ldw").write_bytes(vv1_save(VILLAGERS))
        self.log = game / LOGS / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt"
        self.log.write_bytes(LOG.replace("\n", "\r\n").encode("latin-1"))
        return game

    def test_the_tree_and_the_last_names_window_treat_him_as_born(self):
        game = self.build()
        village = gen.load_village(game, 1, 1)
        cheop = next(p for p in village.people.values() if p.name == "Cheop Bahati")
        silko = next(p for p in village.people.values() if p.name == "Silko Akikai")
        self.assertFalse(cheop.arrived, "a Birth record wins over a backfilled 'How: unknown' Arrived")
        self.assertEqual((village.people[cheop.father].name, village.people[cheop.mother].name),
                         ("Usutu Bahati", "Chapa Wanjiko"))
        self.assertTrue(silko.arrived and silko.how == "Custom Island Event", "a real arrival still counts")
        self.assertIn("born to Chapa Wanjiko and Usutu Bahati", gen.report(village, "Virtual Villagers 1"))

    def test_check_logs_reports_the_pair_as_wrong(self):
        game = self.build()
        checker = tools.load_checker()
        births, _files = checker.births_log(game, 1, 1)
        wrong = checker.backfilled_arrivals_of_the_born(births)
        self.assertEqual([(r.heading, r.child.name) for r in wrong], [("Arrived 2", "Cheop Bahati")])
        rep = checker.Report()
        checker.check_backfilled_arrivals(births, rep)
        self.assertIn("WRONG", rep.render())
        self.assertIn("Arrived 2: Cheop Bahati", rep.render())

    def test_repair_asks_then_removes_it_and_keeps_everything_else_whole(self):
        game = self.build()
        checker = tools.load_checker()
        # A Like and Dislike Words boundary after the record: it moves back with the bytes.
        raw = self.log.read_bytes()
        boundary = raw.index(b"Arrived 3")
        words = game / checker.LOG_WORDS.format(game=1)
        words.parent.mkdir(parents=True)
        name = checker.word_key(str(self.log.relative_to(game)))
        words.write_bytes(f"{boundary}\t{name}\r\n".encode("utf-8"))
        kinds = additions.plan(game, 1, 1)
        kind = next(k for k in kinds if k.id == "born_arrived")
        self.assertEqual(len(kind.questions), 1, "asked about Cheop only, never about Silko")
        question = next(iter(kind.questions.values()))
        self.assertIn("Cheop Bahati", question.text)
        # "Keep it": nothing changes.
        additions.apply(game, kinds, {"born_arrived"}, {question.key: additions.KEEP_IT})
        self.assertEqual(self.log.read_bytes(), raw)
        done = additions.apply(game, kinds, {"born_arrived"}, {question.key: additions.REMOVE_IT})
        after = self.log.read_bytes()
        self.assertNotIn(b"Name: Cheop Bahati", after)
        self.assertIn(b"Child: Cheop Bahati", after, "his Birth record stays")
        self.assertIn(b"\r\nArrived 1\r\n  Name: Silko Akikai", after)
        self.assertIn(b"\r\nArrived 2\r\n  Name: Silko Akikai", after, "the later Arrived record is renumbered")
        self.assertNotIn(b"Arrived 3", after)
        self.assertNotIn(b"\n\n\n", after.replace(b"\r\n", b"\n"), "no blank line is left behind")
        fix = done["born_arrived"][0]
        self.assertEqual(fix.count, 1)
        copy = tools.copy_before_repair(game, self.log, "") .with_name(fix.backup)
        self.assertEqual(copy.read_bytes(), raw, "the file was copied first, into Copies Made Before Repairs")
        bounds = checker.word_boundaries(game, 1)
        self.assertEqual(bounds[name.lower()], after.index(b"Arrived 2\r\n  Name: Silko"),
                         "the boundary moved back with the bytes before it")
        tools.note_word_repair(game, 1, "Village: Kalahuna Tribe 1 (Save 1)", done["born_arrived"],
                               checked=additions.CHECKED["born_arrived"], corrected=additions.ADDED["born_arrived"])
        repairs = next((game / LOGS).rglob("Virtual Villagers 1 Repairs Log 1.txt")).read_text(encoding="latin-1")
        self.assertIn("Backfilled Arrived record removed (the villager was born here)", repairs)
        # Nothing is left to ask, and Check Logs is clean.
        self.assertFalse(next(k for k in additions.plan(game, 1, 1) if k.id == "born_arrived").questions)
        births, _files = checker.births_log(game, 1, 1)
        self.assertFalse(checker.backfilled_arrivals_of_the_born(births))


class CrossCheckTreatsOnlyRealArrivalsAsArrivals(unittest.TestCase):
    def test_the_cross_check_and_its_python_mirror_need_a_known_how(self):
        xc = (ROOT / "native" / "vv1_parentage" / "vv1_crosscheck.inc").read_text(encoding="utf-8")
        self.assertIn("rec.known_how = *how != '\\0' && lstrcmpiA(how, \"unknown\") != 0;", xc)
        self.assertIn("r->kind == 3 && r->known_how", xc)
        checker = (ROOT / "scripts" / "vvfp_consistency_check.py").read_text(encoding="utf-8")
        self.assertIn('r.kind == "arrived" and r.child and real_arrival(r)', checker)


if __name__ == "__main__":
    unittest.main()
