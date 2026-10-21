"""The Lost Children: an Esteemed Elder's totem follows the patcher's own renames, and a totem question is
asked once (src/vv_vv2_totems.py, src/vv_answered_questions.py).

The owner (v1.35.80 preview): "Azizi Kalama I (head 27, body 16) ... this totem could be theirs (the same
first name): Azizi Kalama's totem ... Is this Azizi Kalama I's totem?" kept being asked -- "these should be
only asked once (and answers can be changed under answered questions)".  The statue kept the name the elder
had before Number Duplicate Names numbered them, so it is theirs for certain: no question.  A question that
is still unsure is asked once, its answer kept by who the elder is and what the statue is, never asked again,
and it can be changed or cleared in Answered questions.  Totem colours are numbered 1 to 8.

Each test builds a save folder by hand (a temporary folder) -- never the owner's saves.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_answered_questions as aq  # noqa: E402
import vv_log_decisions as decisions  # noqa: E402
import vv_vv2_totems as vt  # noqa: E402
from test_vv2_totem_repairs import LOGS, Village, crowd, elder_and_totem, person  # noqa: E402

NOW = datetime(2026, 10, 21, 9, 0, 0)


def fact_of(q) -> str:
    """The fact the GUI keeps a totem answer under (vv_fun_patcher_gui._vv2_totems / _totem_fact)."""
    t = q.totem
    return f"sex {q.elder.sex}|totem {t.name}|{t.sex}|{t.head}|{t.body}|{t.lineage}|{t.father}|{t.mother}"


def ask_kept(folder: Path, q, answer: bool, asked: list) -> bool:
    """What the GUI's _ask_kept does, with `answer` standing in for the player."""
    who = ((q.elder.name, q.elder.head, q.elder.body),)
    kept = aq.asked_before(folder, 2, 1, "totem_elders", fact_of(q), who)
    if kept is not None:
        return kept == aq.YES
    asked.append(q.elder.name)
    aq.keep_yes_no(folder, 2, 1, "totem_elders", vt.LABEL_GIVE, fact_of(q), who, q.question(), answer, now=NOW)
    return answer


class TheRenamesAreFollowed(unittest.TestCase):
    def test_the_azizi_case_numbered_by_the_patcher_is_certain(self):
        e, t = elder_and_totem("Azizi Kalama", head=27, body=16)
        e["name"] = "Azizi Kalama I"             # Number Duplicate Names, after the statue was made
        s = vt.survey(Village(self, crowd(3) + [e, t]).folder, 1)
        self.assertEqual((s.missing, s.elder_questions, s.villagers), ([], [], []))

    def test_a_number_given_since_in_another_family_line_is_not_certain(self):
        e, t = elder_and_totem("Azizi Kalama", head=27, body=16, lineage=5)
        e.update(name="Azizi Kalama I", lineage=6)
        s = vt.survey(Village(self, crowd(3) + [e, t]).folder, 1)
        # Not certain: asked (the same first name), never taken as theirs on a guess.
        self.assertEqual([q.why for q in s.elder_questions], ["the same first name"])
        self.assertEqual(s.missing, [])

    def test_two_numbered_namesakes_the_statue_could_be_are_asked_one_to_one(self):
        e1, t = elder_and_totem("Azizi Kalama", head=27, body=16)
        e1["name"] = "Azizi Kalama I"
        e2 = dict(e1, name="Azizi Kalama II")
        s = vt.survey(Village(self, crowd(3) + [e1, e2, t]).folder, 1)
        self.assertEqual([q.elder.name for q in s.elder_questions], ["Azizi Kalama I", "Azizi Kalama II"])

    def test_a_last_name_kept_in_the_log_decisions_is_certain(self):
        e, t = elder_and_totem("Azizi", head=27, body=16)
        e["name"] = "Azizi Kalama"
        v = Village(self, crowd(3) + [e, t])
        decisions.record(v.folder, 2, 1, [{"kind": decisions.ALIAS_KIND, "village": None, "name": "Azizi",
                                           "head": 27, "body": 16, "field": "Azizi Kalama", "verdict": "renamed",
                                           "edited": False}], NOW)
        s = vt.survey(v.folder, 1)
        self.assertEqual((s.missing, s.elder_questions, s.villagers), ([], [], []))
        self.assertIn(("Azizi", "Azizi Kalama", 27, 16), vt._renames(v.folder, 1))

    def test_a_renamed_line_of_the_repairs_made_log_is_certain(self):
        e, t = elder_and_totem("Azizi", head=27, body=16)
        e["name"] = "Mosi Kalama"                 # a first name the statue does not share
        v = Village(self, crowd(3) + [e, t])
        path = v.folder / LOGS / "Repairs Made" / "Virtual Villagers 2 Repairs Log 1.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes("Village: Tribe (Save 1)\nRepair 1\n  Renamed: Azizi (head 27, body 16) -> Mosi Kalama\n\n"
                         .replace("\n", "\r\n").encode("latin-1"))
        self.assertIn(("Azizi", "Mosi Kalama", 27, 16), vt._renames(v.folder, 1))
        s = vt.survey(v.folder, 1)
        self.assertEqual((s.missing, s.elder_questions, s.villagers), ([], [], []))


class AskedOnce(unittest.TestCase):
    def _unsure(self):
        e1 = person("Kaki Jumapili", elder=True, head=3, body=4)
        e2 = person("Kaki Wambui", elder=True, head=5, body=6)
        t = person("Kaki", totem=True, health=0, head=1, body=1)
        return Village(self, crowd(3) + [e1, e2, t])

    def test_an_unsure_question_is_asked_once_and_its_answer_kept(self):
        v = self._unsure()
        asked: list[str] = []
        s = vt.survey(v.folder, 1)
        kept = vt.ask(s, lambda q: ask_kept(v.folder, q, False, asked))
        self.assertEqual(asked, ["Kaki Jumapili", "Kaki Wambui"])
        self.assertEqual(kept, set())
        # The next Repair: nothing is asked, the same answers are used.
        asked.clear()
        again = vt.ask(vt.survey(v.folder, 1), lambda q: ask_kept(v.folder, q, True, asked))
        self.assertEqual((asked, again), ([], set()))

    def test_a_yes_is_kept_too_and_listed_to_change_or_clear(self):
        v = self._unsure()
        asked: list[str] = []
        kept = vt.ask(vt.survey(v.folder, 1), lambda q: ask_kept(v.folder, q, True, asked))
        self.assertEqual(asked, ["Kaki Jumapili"])
        self.assertEqual(len(kept), 1)
        rows = [r for r in aq.listing(v.folder, 2, 1, []) if "Is this Kaki Jumapili's totem?" in r.text]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].answer, rows[0].options), (aq.YES, [aq.YES, aq.NO]))
        # Changed to No in Answered questions: used from then on, still not asked.
        aq.change(v.folder, 2, 1, {rows[0].ident: aq.NO}, set(), now=NOW)
        asked.clear()
        first = vt.survey(v.folder, 1).elder_questions[0]
        self.assertFalse(ask_kept(v.folder, first, True, asked))
        self.assertEqual(asked, [])
        # Cleared: asked again.
        row = [r for r in aq.listing(v.folder, 2, 1, []) if "Is this Kaki Jumapili's totem?" in r.text][0]
        aq.change(v.folder, 2, 1, {}, {row.ident}, now=NOW)
        self.assertTrue(ask_kept(v.folder, first, True, asked))
        self.assertEqual(asked, ["Kaki Jumapili"])

    def test_the_gui_keeps_the_totem_answer_by_identity(self):
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        method = gui[gui.index("    def _vv2_totems("):gui.index("    def _restore_lost_titles(")]
        self.assertIn('"totem_elders"', method)
        self.assertIn("self._ask_kept(", method)
        self.assertIn('f"sex {q.elder.sex}|{self._totem_fact(q.totem)}"', method)
        fact = gui[gui.index("    def _totem_fact("):gui.index("    def _ask_kept(")]
        self.assertNotIn("record", fact.split('"""')[-1])     # never the record number


class TheColoursAreNumbered(unittest.TestCase):
    def test_one_to_eight_from_the_left(self):
        self.assertEqual(vt.FACES, tuple(f"colour {n}" for n in range(1, 9)))
        self.assertEqual(vt.face(0), "colour 1")
        self.assertEqual(vt.face(41), "colour 2")

    def test_no_totem_is_described_by_its_looks(self):
        words = ("brown face", "green figure", "red crest", "yellow and purple", "red headdress", "navy face",
                 "carved wood", "grinning face")
        for rel in ("src/vv_vv2_totems.py", "src/vv_vv2_totem_store.py", "src/vv_fun_patcher_gui.py",
                    "native/vvfp_story_upgrades/story_c2.inc", "native/vvfp_island_events/island_event_more.inc",
                    "README.md", "How to Use.txt"):
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for w in words:
                self.assertNotIn(w, text, f"{rel}: {w}")

    def test_the_window_shows_the_number_under_each_picture(self):
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        method = gui[gui.index("    def _totem_colour("):gui.index("    def _restore_lost_titles(")]
        self.assertIn('text=str(face + 1), compound="top"', method)

    def test_a_totem_is_listed_with_its_colour_number(self):
        import vv_vv2_totem_store as store
        source = (ROOT / "src" / "vv_vv2_totem_store.py").read_text(encoding="utf-8")
        self.assertIn("return f\"{self.name}'s totem ({totems.face(self.type)}, head {self.head}, body {self.body})\"",
                      source)
        self.assertTrue(hasattr(store, "LABEL_COLOUR"))


if __name__ == "__main__":
    unittest.main()
