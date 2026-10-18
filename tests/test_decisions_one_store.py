"""The two "Retroactively edit records? No" stores are one (all five games).

An answer of No used to be kept in two places: the decisions file
("Log Decisions - Save n.json", src/vv_log_decisions.py) for a backfilled record of a villager
already recorded, and a second text file ("Contradictions Left - Save n.txt",
src/vv_log_contradictions.py) for a Death or Repair number used twice and the same backfilled
record when found by Check Logs.  Both are the same answer, so they are kept in the decisions
file now; the text file is still read (an answer given before holds), its lines are copied into
the decisions file the first time something new is written, and it is never written to,
rewritten or deleted.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_log_contradictions as contra  # noqa: E402
import vv_log_decisions as decisions  # noqa: E402
from test_log_contradictions import DATA, LOGS, VILLAGE, Folder, arrived, birth, death  # noqa: E402

CHECKS = f"{DATA}\\Log Checks"
OLD_CHECKS = f"{DATA}\\Cross-Check"


def txt(game: int, slot: int = 1) -> str:
    return f"Virtual Villagers {game} Contradictions Left - Save {slot}.txt"


def store(f: Folder, game: int, slot: int = 1) -> Path:
    return decisions.path(f.path, game, slot)          # the save's own folder for a fresh save (src/vv_save_layout.py)


def two_contradictions(game: int) -> Folder:
    f = Folder(game)
    f.births(birth("Cheop Bahati", 4, 15) + arrived(11, "Cheop Bahati", 4, 15, how="Founder"))
    f.write(f"{LOGS}\\Deaths and Disappearances\\Virtual Villagers {game} Deaths Log 1.txt",
            VILLAGE + "\n" + death(15, "Hawa", 17, 5) + death(15, "Silko", 4, 14))
    return f


def answered_no(f: Folder, game: int) -> list:
    kinds = [contra.plan(f.path, game, 1)]
    answers = {k: (contra.RETRO_NO if k.startswith("retro|") else q.options[0])
               for kind in kinds for k, q in kind.questions.items()}
    return kinds, answers


class OneStoreTests(unittest.TestCase):
    def test_a_no_is_written_to_the_decisions_file_and_never_to_the_text_file(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                f = two_contradictions(game)
                kinds, answers = answered_no(f, game)
                new = contra.remember(f.path, game, 1, kinds, answers)
                self.assertEqual(len(new), 2)
                data = json.loads(store(f, game).read_text(encoding="utf-8"))
                left = {d["field"] for d in data["decisions"] if d["kind"] == decisions.LEFT_KIND}
                self.assertEqual(left, set(new))
                self.assertEqual(list((f.path / CHECKS).glob("*Contradictions Left*")), [],
                                 "nothing is written to the second store any more")
                self.assertEqual([x for x in contra.find(f.path, game, 1) if x.wrong], [])
                self.assertEqual(contra.plan(f.path, game, 1).questions, {}, "...and not asked again")
                self.assertEqual(contra.remember(f.path, game, 1, kinds, answers), [], "a second No adds nothing")

    def test_an_answer_in_the_earlier_text_file_still_holds(self):
        for game in (1, 2, 3, 4, 5):
            for folder in (CHECKS, OLD_CHECKS):         # the file under both names an earlier build used
                with self.subTest(game=game, folder=folder):
                    f = two_contradictions(game)
                    idents = [x.ident for x in contra.find(f.path, game, 1) if x.wrong]
                    self.assertEqual(len(idents), 2)
                    f.write(f"{folder}\\{txt(game)}", "".join(i + "\n" for i in idents))
                    self.assertEqual(decisions.left_alone(f.path, game, 1), set(idents))
                    self.assertEqual([x for x in contra.find(f.path, game, 1) if x.wrong], [])
                    self.assertEqual(contra.plan(f.path, game, 1).questions, {})

    def test_the_earlier_files_lines_are_copied_in_and_the_file_is_left_exactly_as_it_was(self):
        f = two_contradictions(1)
        idents = sorted(x.ident for x in contra.find(f.path, 1, 1) if x.wrong)
        old = f.write(f"{CHECKS}\\{txt(1)}", idents[0] + "\n")
        before = old.read_bytes()
        decisions.remember_left(f.path, 1, 1, [idents[1]])
        data = json.loads(store(f, 1).read_text(encoding="utf-8"))
        self.assertEqual({d["field"] for d in data["decisions"] if d["kind"] == decisions.LEFT_KIND}, set(idents),
                         "the older answer comes along with the new one")
        self.assertEqual(old.read_bytes(), before, "the text file is never rewritten or deleted")

    def test_the_other_decisions_in_the_file_are_untouched_by_remembering(self):
        f = two_contradictions(1)
        entry = {"kind": "born_arrived", "village": VILLAGE, "name": "Kai", "head": 3, "body": 3,
                 "verdict": "remove", "edited": False}
        decisions.record(f.path, 1, 1, [entry])
        decisions.remember_left(f.path, 1, 1, ["death_number|15|Silko|1600"])
        self.assertEqual(decisions.decided(f.path, 1, 1, "born_arrived", "remove", {VILLAGE}), {("Kai", 3, 3)})
        self.assertEqual(decisions.decided(f.path, 1, 1, decisions.LEFT_KIND, "leave"), {(None, None, None)})
        self.assertEqual(decisions.left_alone(f.path, 1, 1), {"death_number|15|Silko|1600"})

    def test_a_decisions_file_that_cannot_be_read_is_set_aside_not_written_over(self):
        f = two_contradictions(1)
        bad = store(f, 1)
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"{ this is not json")
        self.assertEqual(decisions.left_alone(f.path, 1, 1), set(), "read as holding nothing")
        decisions.remember_left(f.path, 1, 1, ["repair_number|x|1"])
        aside = bad.with_name(bad.name + ".unreadable")
        self.assertEqual(aside.read_bytes(), b"{ this is not json", "what it held is kept beside the new file")
        self.assertEqual(decisions.left_alone(f.path, 1, 1), {"repair_number|x|1"})
        bad.write_bytes(b"[1, 2]")                       # unreadable again: a second name
        decisions.remember_left(f.path, 1, 1, ["repair_number|y|2"])
        self.assertEqual(bad.with_name(bad.name + ".unreadable1").read_bytes(), b"[1, 2]")

    def test_start_over_and_other_readers_are_unaffected_by_the_new_kind(self):
        """A reader of another kind never sees these entries; one decision per identity."""
        f = Folder(1)
        decisions.remember_left(f.path, 1, 1, ["a|1", "a|1", "b|2"])
        entries = [d for d in decisions.load(f.path, 1, 1) if d["kind"] == decisions.LEFT_KIND]
        self.assertEqual(sorted(d["field"] for d in entries), ["a|1", "b|2"])
        self.assertEqual(decisions.decided(f.path, 1, 1, "grave", "leave"), set())
        self.assertEqual(decisions.decided(f.path, 1, 1, "born_arrived", "remove"), set())

    def test_the_second_store_is_gone_from_the_contradictions_module(self):
        self.assertFalse(hasattr(contra, "KEPT"), "the module no longer owns a file of its own")
        self.assertIn("Contradictions Left", (ROOT / "src" / "vv_log_decisions.py").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
