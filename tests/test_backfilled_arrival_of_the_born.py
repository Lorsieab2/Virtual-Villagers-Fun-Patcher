"""A backfilled "How: unknown" Arrived record never outweighs what the log already records (all five
games).

The owner's A New Home log holds, beside the records that are right, three records the arrival
backfill wrote ("How: unknown / Note: Recorded afterwards (arrived before this log existed)") when it
could not see the villager's own record:

* Cheop Bahati: a Birth record (written as "Cheop" before Last Names) and a backfilled Arrived 11;
* the Golden Child Lulu Chuchip: a Birth record (added later by Repair) and a backfilled Arrived 13;
* Hoani Chuchip: a real Arrived 8 (How: Barrel of Babies, written as "Hoani") and a backfilled
  Arrived 12.

So, in every game:

* the Family Tree Maker, the Matchmaker and the last-names window treat a villager with a Birth record
  as born, and a backfilled "How: unknown" never replaces a real How;
* Check Logs reports each such backfilled record as WRONG;
* Repair Saves & Logs asks about each ("Remove" / "Keep it"), then "Retroactively edit records?":
  Yes takes it out (the file copied first, a Repairs Made entry, the later "Arrived <n>"
  renumbered, the Like and Dislike Words boundary moved); No leaves the log exactly as it is and
  remembers the answer (src/vv_log_decisions.py), which the readers and Check Logs then follow;
* the arrival backfill matches a record named by the first name alone
  (native/parentage_export/arrival_backfill.inc; tests/test_arrived_records.py runs it).

Fixtures are built here; no file outside the repository is read.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy as gen  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_decisions as decisions  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_vv1_expected_father import vv1_save  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
VILLAGE = "Village: Kalahuna Tribe 1 (Save 1)"

# name, male, family, head, body, carrying
VILLAGERS = [
    ("Usutu Bahati", True, 30, 7, 2, False),
    ("Chapa Wanjiko", False, 17, 18, 9, False),
    ("Cheop Bahati", True, 30, 4, 15, False),
    ("Hoani Chuchip", True, 44, 11, 2, False),
]

BACKFILL = "  How: unknown\n  Note: Recorded afterwards (arrived before this log existed)\n"
LOG = f"""{VILLAGE}
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
  Name: Hoani Chuchip
  Age at arrival: 40
  Sex: Male
  Head: 11
  Body: 2
  Likes: (none)
  Dislikes: (none)
  How: Barrel of Babies

Arrived 2
  Name: Cheop Bahati
  Age at arrival: (unknown)
  Sex: Male
  Head: 4
  Body: 15
{BACKFILL}
Arrived 3
  Name: Hoani Chuchip
  Age at arrival: (unknown)
  Sex: Male
  Head: 11
  Body: 2
{BACKFILL}
Arrived 4
  Name: Usutu Bahati
  Age at arrival: (unknown)
  Sex: Male
  Head: 7
  Body: 2
  How: Founder
  Note: Recorded afterwards (arrived before this log existed)

"""


def answers_for(kind, retro: str) -> dict[str, str]:
    out = {}
    for key in kind.questions:
        out[key] = retro if key.endswith("|retro") else additions.REMOVE_IT
    return out


class AllFiveGamesTests(unittest.TestCase):
    """The same records in each game's own log: found, and on Yes removed and renumbered."""

    def test_each_game(self):
        checker = tools.load_checker()
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
                log = folder / LOGS / "Births and Conceptions" / f"Virtual Villagers {game} Births and Conceptions Log 1.txt"
                log.parent.mkdir(parents=True)
                log.write_bytes(LOG.replace("\n", "\r\n").encode("latin-1"))
                births, _files = checker.births_log(folder, game, 1)
                found = checker.redundant_backfilled_arrivals(births, {})
                self.assertEqual([(r.heading, r.child.name) for r, _what in found],
                                 [("Arrived 2", "Cheop Bahati"), ("Arrived 3", "Hoani Chuchip")])
                self.assertEqual([what for _r, what in found], ["a Birth record", "Arrived 1 (How: Barrel of Babies)"])
                # Two villagers alive with one look need two records: the backfill is then not offered.
                self.assertEqual(checker.redundant_backfilled_arrivals(births, {("Hoani Chuchip", 11, 2): 2})[1:], [])
                kind = additions.plan_backfilled_arrivals(folder, game, 1, {}, None)
                self.assertEqual(len(kind.questions), 4, "two records, each with its Retroactively question")
                additions.apply(folder, [kind], {"born_arrived"}, answers_for(kind, additions.RETRO_YES))
                text = log.read_bytes().decode("latin-1")
                self.assertEqual(text.count("Name: Cheop Bahati"), 0)
                self.assertEqual(text.count("Name: Hoani Chuchip"), 1)
                self.assertIn("Arrived 1\r\n  Name: Hoani Chuchip", text)
                self.assertIn("Arrived 2\r\n  Name: Usutu Bahati", text, "the founder renumbered after them")
                self.assertNotIn("Arrived 3", text)


class AnNewHomeVillageTests(unittest.TestCase):
    def build(self) -> Path:
        game = Path(self.enterContext(tempfile.TemporaryDirectory())) / "Virtual Villagers - A New Home"
        (game / LOGS / "Births and Conceptions").mkdir(parents=True)
        (game / DATA).mkdir(parents=True)
        (game / "Virtual Villagers1.ldw").write_bytes(vv1_save(VILLAGERS))
        self.log = game / LOGS / "Births and Conceptions" / "Virtual Villagers 1 Births and Conceptions Log 1.txt"
        self.log.write_bytes(LOG.replace("\n", "\r\n").encode("latin-1"))
        return game

    def test_the_tree_and_the_last_names_window_follow_the_firm_records(self):
        game = self.build()
        village = gen.load_village(game, 1, 1)
        cheop = next(p for p in village.people.values() if p.name == "Cheop Bahati")
        hoani = next(p for p in village.people.values() if p.name == "Hoani Chuchip")
        self.assertFalse(cheop.arrived, "a Birth record wins over a backfilled 'How: unknown' Arrived")
        self.assertEqual((village.people[cheop.father].name, village.people[cheop.mother].name),
                         ("Usutu Bahati", "Chapa Wanjiko"))
        self.assertTrue(hoani.arrived and hoani.how == "Barrel of Babies", "the real How is kept")
        self.assertIn("born to Chapa Wanjiko and Usutu Bahati", gen.report(village, "Virtual Villagers 1"))

    def test_check_logs_reports_both_kinds_as_wrong(self):
        game = self.build()
        report = tools.check_logs(game, 1, 1).text
        self.assertIn("Arrived 2: Cheop Bahati (head 4, body 15) is already recorded by a Birth record", report)
        self.assertIn("Arrived 3: Hoani Chuchip (head 11, body 2) is already recorded by Arrived 1 (How: Barrel of "
                      "Babies)", report)
        self.assertNotIn("Usutu Bahati (head", report, "a founder's own record is no duplicate")

    def test_yes_edits_the_records_safely(self):
        game = self.build()
        checker = tools.load_checker()
        raw = self.log.read_bytes()
        boundary = raw.index(b"Arrived 4")
        words = game / checker.LOG_WORDS.format(game=1)
        words.parent.mkdir(parents=True)
        name = checker.word_key(str(self.log.relative_to(game)))
        words.write_bytes(f"{boundary}\t{name}\r\n".encode("utf-8"))
        kinds = additions.plan(game, 1, 1)
        kind = next(k for k in kinds if k.id == "born_arrived")
        self.assertEqual(len(kind.questions), 4)
        # "Keep it": nothing changes, nothing is remembered.
        keep = {key: (additions.RETRO_YES if key.endswith("|retro") else additions.KEEP_IT) for key in kind.questions}
        additions.apply(game, kinds, {"born_arrived"}, keep)
        self.assertEqual(self.log.read_bytes(), raw)
        self.assertEqual(additions.resolve_decisions(kinds, {"born_arrived"}, keep), [])
        done = additions.apply(game, kinds, {"born_arrived"}, answers_for(kind, additions.RETRO_YES))
        after = self.log.read_bytes()
        self.assertNotIn(b"Name: Cheop Bahati", after)
        self.assertIn(b"Child: Cheop Bahati", after, "his Birth record stays")
        self.assertEqual(after.count(b"Name: Hoani Chuchip"), 1, "the real Arrived record stays")
        self.assertIn(b"Arrived 2\r\n  Name: Usutu Bahati", after, "the later Arrived record is renumbered")
        self.assertNotIn(b"Arrived 3", after)
        self.assertNotIn(b"\n\n\n", after.replace(b"\r\n", b"\n"), "no blank line is left behind")
        fix = done["born_arrived"][0]
        self.assertEqual(fix.count, 2)
        copy = tools.copy_before_repair(game, self.log, "").with_name(fix.backup)
        self.assertEqual(copy.read_bytes(), raw, "the file was copied first, into Copies Made Before Repairs")
        self.assertEqual(checker.word_boundaries(game, 1)[name.lower()], after.index(b"Arrived 2\r\n  Name: Usutu"),
                         "the boundary moved back with the bytes before it")
        tools.note_word_repair(game, 1, VILLAGE, done["born_arrived"],
                               checked=additions.CHECKED["born_arrived"], corrected=additions.ADDED["born_arrived"])
        repairs = next((game / LOGS).rglob("Virtual Villagers 1 Repairs Log 1.txt")).read_text(encoding="latin-1")
        self.assertIn("Duplicate backfilled Arrived record removed", repairs)
        self.assertFalse(next(k for k in additions.plan(game, 1, 1) if k.id == "born_arrived").questions)
        self.assertIn("no villager the log already records", tools.check_logs(game, 1, 1).text)

    def test_no_leaves_the_log_and_remembers_the_answer(self):
        game = self.build()
        raw = self.log.read_bytes()
        kinds = additions.plan(game, 1, 1)
        kind = next(k for k in kinds if k.id == "born_arrived")
        answers = answers_for(kind, additions.RETRO_NO)
        done = additions.apply(game, kinds, {"born_arrived"}, answers)
        self.assertEqual(self.log.read_bytes(), raw, "the log is left exactly as it is")
        self.assertFalse(done.get("born_arrived"))
        decisions.record(game, 1, 1, additions.resolve_decisions(kinds, {"born_arrived"}, answers))
        stored = json.loads(decisions.path(game, 1, 1).read_text(encoding="utf-8"))
        self.assertEqual(stored["version"], 1)
        self.assertEqual(sorted((d["name"], d["verdict"], d["edited"], d["village"]) for d in stored["decisions"]),
                         [("Cheop Bahati", "remove", False, VILLAGE), ("Hoani Chuchip", "remove", False, VILLAGE)])
        # The readers follow the answer; Check Logs notes it instead of calling it wrong; not asked again.
        village = gen.load_village(game, 1, 1)
        cheop = next(p for p in village.people.values() if p.name == "Cheop Bahati")
        hoani = next(p for p in village.people.values() if p.name == "Hoani Chuchip")
        self.assertFalse(cheop.arrived)
        self.assertEqual(hoani.how, "Barrel of Babies")
        report = tools.check_logs(game, 1, 1).text
        self.assertNotIn("is already recorded by", report)
        self.assertIn("a backfilled Arrived record you decided to disregard", report)
        self.assertFalse(next(k for k in additions.plan(game, 1, 1) if k.id == "born_arrived").questions)
        # A decision for another village of the slot (after Start Over) is not this village's.
        self.assertEqual(decisions.decided(game, 1, 1, "born_arrived", "remove", {"Village: Other (Save 1)"}), set())


class NoGame:
    def find(self, exe_name):
        return []


class RepairSavesAndLogsTests(AnNewHomeVillageTests):
    """Through Repair Saves & Logs itself (vv_log_tools.approve_repair), both answers."""

    def run_repair(self, retro: str) -> Path:
        game = self.build()
        kinds = additions.plan(game, 1, 1)
        kind = next(k for k in kinds if k.id == "born_arrived")
        tools.approve_repair(game, 1, 1, NoGame(), chosen={"born_arrived"}, answers=answers_for(kind, retro),
                             kinds=kinds, rearm=False)
        return game

    def test_yes_through_the_repair(self):
        game = self.run_repair(additions.RETRO_YES)
        self.assertNotIn(b"Name: Cheop Bahati", self.log.read_bytes())
        self.assertFalse(decisions.path(game, 1, 1).exists(), "nothing to remember: the records were edited")
        repairs = next((game / LOGS).rglob("Virtual Villagers 1 Repairs Log 1.txt")).read_text(encoding="latin-1")
        self.assertIn("Duplicate backfilled Arrived record removed", repairs)

    def test_no_through_the_repair(self):
        raw = LOG.replace("\n", "\r\n").encode("latin-1")
        game = self.run_repair(additions.RETRO_NO)
        self.assertEqual(self.log.read_bytes(), raw)
        self.assertEqual(decisions.decided(game, 1, 1, "born_arrived", "remove"),
                         {("Cheop Bahati", 4, 15), ("Hoani Chuchip", 11, 2)})


class CrossCheckTreatsOnlyRealArrivalsAsArrivals(unittest.TestCase):
    def test_the_cross_check_and_its_python_mirror_need_a_known_how(self):
        xc = (ROOT / "native" / "vv1_parentage" / "vv1_crosscheck.inc").read_text(encoding="utf-8")
        self.assertIn("rec.known_how = *how != '\\0' && lstrcmpiA(how, \"unknown\") != 0;", xc)
        self.assertIn("r->kind == 3 && r->known_how", xc)
        checker = (ROOT / "scripts" / "vvfp_consistency_check.py").read_text(encoding="utf-8")
        self.assertIn('r.kind == "arrived" and r.child and real_arrival(r)', checker)


if __name__ == "__main__":
    unittest.main()
