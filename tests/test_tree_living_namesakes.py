"""Two living villagers of one name and look, default fathers, retyped title lines and the Matchmaker's numbering
(the owner's answers, v1.35.85).

* SHOW BOTH, LINK BY AGE.  The Secret City's 256 copy held two living "Tepeu Tamikai" (head 12, body 5), aged 1583
  and 120: the tree showed one, 6 years old, with the younger one's parents, as the father of a 39-year-old, and
  the elder "(left the village)".  Each save record is now a villager of its own; a child is linked to the one old
  enough to be the parent at the birth; when more than one could be, the Family Tree Maker asks, never guesses.
* A RETYPED TITLE LINE keeps the player's words, but its villager counts and date are those of today's tree.
* DEFAULT FATHERS ("?", "Joey", "Unknown") are not numbered and not counted.
* THE MATCHMAKER numbers duplicate names only when the tree's numbering is on.

Fixtures are made here (tests/test_last_names_rename.py's save layout); nothing outside is read.
"""
from __future__ import annotations

import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_answered_questions as aq  # noqa: E402
import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_genealogy import village as hand_village  # noqa: E402
from test_last_names_rename import DATA, TABLE, entry  # noqa: E402

TEPEU = ("Tepeu Tamikai", 12, 5)


def aged(record: bytes, age: int) -> bytes:
    e = bytearray(record)
    struct.pack_into("<i", e, 0x14 - 0x10, age)
    return bytes(e)


def save(folder: Path, records: list[bytes]) -> Path:
    (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
        bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(records) + bytes(64)))
    (folder / DATA).mkdir(parents=True, exist_ok=True)
    return folder


def tepeu(age: int, father: tuple, mother: tuple) -> bytes:
    return aged(entry(TEPEU[0], 0, 37, TEPEU[1], TEPEU[2], father=father, mother=mother), age)


class ShowBothLinkByAge(unittest.TestCase):
    def folder(self) -> Path:
        return Path(self.enterContext(tempfile.TemporaryDirectory()))

    def tepeu_case(self) -> Path:
        """The owner's shape: the elder (1583) and a boy of 120 share the name and look; Ponui (782) and Hakuna
        (163) name "Tepeu Tamikai" as their father."""
        return save(self.folder(), [
            aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
            tepeu(1583, ("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
            aged(entry("Ponui Kalama", 0, 37, 10, 17, father=TEPEU, mother=("Parai Tokidoki", 7, 7)), 782),
            aged(entry("Hakuna Murago", 1, 3, 12, 28, father=TEPEU, mother=("Parai Tokidoki", 7, 7)), 163),
            tepeu(120, ("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
        ])

    def tepeus(self, v: gen.Village) -> list:
        return sorted((p for p in v.people.values() if p.key == TEPEU), key=lambda p: -(p.age or 0))

    def name(self, v: gen.Village, pid) -> str | None:
        return v.people[pid].name if pid is not None else None

    def test_two_living_records_are_two_people_with_their_own_age_and_parents(self) -> None:
        v = gen.load_village(self.tepeu_case(), 3, 1)
        elder, boy = self.tepeus(v)
        self.assertTrue(elder.alive and boy.alive, "neither is shown as having left")
        self.assertEqual((elder.age, boy.age), (1583, 120))
        self.assertEqual((self.name(v, elder.father), self.name(v, elder.mother)), ("Pichu Tamikai", "Toga Helaku"))
        self.assertEqual((self.name(v, boy.father), self.name(v, boy.mother)), ("Oro Kenobi", "Coral Guedado"))
        self.assertEqual(len(v.living()), 5)

    def test_each_child_goes_to_the_one_old_enough(self) -> None:
        v = gen.load_village(self.tepeu_case(), 3, 1)
        elder, boy = self.tepeus(v)
        for child in ("Ponui Kalama", "Hakuna Murago"):
            p = next(q for q in v.people.values() if q.name == child)
            self.assertEqual(p.father, elder.id, child)
        self.assertEqual(v.children_of(boy.id), [])
        self.assertEqual(v.parent_questions, [], "nothing to ask: only the elder was of age")

    def test_a_namesake_fathered_by_a_namesake_links_to_the_elder(self) -> None:
        """Codex, PR #653: the younger Tepeu names "Tepeu Tamikai" as his father and comes first in the save; he
        is never his own father, and links to the elder, the only one old enough."""
        v = gen.load_village(save(self.folder(), [
            aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
            tepeu(120, TEPEU, ("Parai Tokidoki", 7, 7)),
            tepeu(1583, ("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
        ]), 3, 1)
        elder, boy = self.tepeus(v)
        self.assertNotEqual(boy.father, boy.id, "never his own father")
        self.assertEqual(boy.father, elder.id)
        self.assertEqual(v.parent_questions, [], "only the elder could be his father")

    def test_relationships_see_two(self) -> None:
        """The Villager Info tab's Relationships (src/vv_relationships.py) work by villager id: the elder is the
        children's father, the boy is nobody's, and the two namesakes are not related to each other."""
        import vv_relationships as rel
        v = gen.load_village(self.tepeu_case(), 3, 1)
        elder, boy = self.tepeus(v)
        r = rel.Relationships(v)
        kids = {q.id for q in v.people.values() if q.name in ("Ponui Kalama", "Hakuna Murago")}
        self.assertEqual({x.pid for x in r.of(elder.id) if x.group == "Children"}, kids)
        self.assertNotIn("Children", [x.group for x in r.of(boy.id)])
        self.assertEqual([x for x in r.of(elder.id) if x.pid == boy.id], [])
        self.assertEqual([x for x in r.of(boy.id) if x.pid == elder.id], [])
        for kid in kids:
            fathers = [x.pid for x in r.of(kid) if x.term == "Father"]
            self.assertEqual(fathers, [elder.id])

    def test_numbering_the_matchmaker_and_the_tree_see_two(self) -> None:
        v = gen.load_village(self.tepeu_case(), 3, 1)
        elder, boy = self.tepeus(v)
        self.assertNotEqual(elder.number, boy.number)
        self.assertIsNotNone(elder.number)
        named = gen.duplicate_names(v)
        self.assertEqual(sorted(named[p.id] for p in (elder, boy)), ["Tepeu Tamikai I", "Tepeu Tamikai II"])
        self.assertNotEqual(ft.entry_key(v, elder), ft.entry_key(v, boy), "each keeps their own tree edits")
        self.assertEqual(ft.entry_key(v, elder), "Tepeu Tamikai|12|5", "the elder keeps the key earlier edits used")
        men, _women = gen.candidates(v, gen.Rules(allow_50_plus=True))
        self.assertIn(elder.id, [m.id for m in men])
        self.assertEqual(gen.relationship(v, elder.id, boy.id), "no recorded common ancestor")
        lay = ft.layout(v, ft.Edits())
        self.assertIn(elder.id, lay.x)
        self.assertIn(boy.id, lay.x)

    def test_both_old_enough_is_asked_never_guessed_and_the_answer_is_kept(self) -> None:
        folder = save(self.folder(), [
            aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
            tepeu(1583, ("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
            aged(entry("Ponui Kalama", 0, 37, 10, 17, father=TEPEU, mother=("Parai Tokidoki", 7, 7)), 300),
            tepeu(1000, ("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
        ])
        v = gen.load_village(folder, 3, 1)
        ponui = next(q for q in v.people.values() if q.name == "Ponui Kalama")
        self.assertIsNone(ponui.father, "both could be his father: none is guessed")
        self.assertEqual(len(v.parent_questions), 1)
        q = v.parent_questions[0]
        self.assertEqual((q.child, q.parent, q.label), (ponui.key, TEPEU, "Father"))
        self.assertEqual([t.split(" (")[0] for t in q.texts], ["The oldest", "The second oldest"])
        aq.keep_parent(folder, 3, 1, q.child, q.parent, q.label, ["The oldest", "The second oldest"],
                       "The second oldest", q.text)
        v = gen.load_village(folder, 3, 1)
        ponui = next(p for p in v.people.values() if p.name == "Ponui Kalama")
        younger = self.tepeus(v)[1]
        self.assertEqual(ponui.father, younger.id, "the player's answer links him")
        self.assertEqual(v.parent_questions, [])

    def test_could_be_parent_by_the_games_age(self) -> None:
        old = gen.Person(1, "P", 1, 1, age=1583, alive=True)
        boy = gen.Person(2, "P", 1, 1, age=120, alive=True)
        child = gen.Person(3, "C", 2, 2, age=782, alive=True)
        self.assertTrue(gen.could_be_parent(old, child))
        self.assertFalse(gen.could_be_parent(boy, child))
        gone = gen.Person(4, "D", 3, 3, age=900, alive=False, gone="died")
        self.assertTrue(gen.could_be_parent(old, gone))
        self.assertFalse(gen.could_be_parent(boy, gone), "a boy of 6 was never of age")
        self.assertTrue(gen.could_be_parent(gen.Person(5, "Q", 1, 1, age=360, alive=True),
                                            gen.Person(6, "U", -1, -1, upcoming=True)))


class RetypedTitleLine(unittest.TestCase):
    def test_counts_and_date_follow_the_tree_the_words_stay(self) -> None:
        v = hand_village()
        e = ft.Edits(subtitle="Kalahuna Tribe 3: Nature Faction (Save 1) -- 8 villagers known, 8 living -- "
                              "2026-10-21 20:32", title="My own tree")
        lay = ft.layout(v, e)
        title, subtitle = ft.title_lines(lay, "VV3")
        self.assertEqual(title, "My own tree")
        self.assertTrue(subtitle.startswith("Kalahuna Tribe 3: Nature Faction (Save 1) -- 12 villagers known, "
                                            "12 living -- "), subtitle)
        self.assertNotIn("2026-10-21 20:32", subtitle)
        self.assertRegex(subtitle, r"-- \d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(e.subtitle.count("8 villagers known"), 1, "the saved words are not changed")
        free = ft.Edits(subtitle="Our family, est. 2020")
        self.assertEqual(ft.title_lines(ft.layout(v, free), "VV3")[1], "Our family, est. 2020")


def with_default_father() -> gen.Village:
    v = hand_village()
    v.game = 2
    v.people[20] = gen.Person(20, "?", 0, 0, sex="Male", first_seen=v.people[1].first_seen)
    v.people[21] = gen.Person(21, "Gong", 21, 21, sex="Female", age=5 * gen.UNITS_PER_YEAR, alive=True,
                              father=20, mother=2, first_seen=v.people[1].first_seen)
    for p in v.people.values():
        p.placeholder = gen.is_placeholder_father(2, p)
    gen._generations(v, {v.people[1].first_seen: set(v.people)})
    gen.number_people(v)
    return v


class DefaultFathersAreNamesOnly(unittest.TestCase):
    def test_not_numbered_not_counted(self) -> None:
        v = with_default_father()
        q = v.people[20]
        self.assertTrue(q.placeholder)
        self.assertIsNone(q.number)
        self.assertEqual(sorted(p.number for p in v.villagers()), list(range(1, 14)), "the others run on, no gap")
        lay = ft.layout(v, ft.Edits())
        self.assertIn(20, lay.x, "still drawn, as the father the records name")
        self.assertEqual(ft.default_text(lay, q), ["?"], "his name only")
        g = q.generation
        self.assertEqual(sum(1 for p in v.villagers() if p.generation == g),
                         int(ft.default_label_parts(lay, g)["total"].split()[0]))
        self.assertIn("13 villagers known", ft.title_lines(lay, "VV2")[1])
        report = gen.report(v, "VV2")
        self.assertIn("Generation I: 5 villagers (5 living)", report)     # A, B, C, D and X: never "?"

    def test_renumbering_with_an_order_skips_him(self) -> None:
        v = with_default_father()
        e = ft.Edits(orders={"1": ["D|4|4", "A|1|1"]})
        ft.arrange(v, e)
        self.assertIsNone(v.people[20].number)
        self.assertEqual(v.people[4].number, 1)


class MatchmakerNumberingFollowsTheTree(unittest.TestCase):
    def build(self) -> Path:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        return save(folder, [
            aged(entry("Soda", 1, 5, 7, 7), 500),
            aged(entry("Soda", 1, 6, 7, 7), 520),
            aged(entry("Kai", 0, 8, 9, 9), 510),
        ])

    def report(self, folder: Path, numbering: bool) -> str:
        ft.Edits(number_names=numbering).save(ft.Edits.path(folder, 3, 1))
        return ft.write_pairs(folder, 3, 1, gen.Rules(), "VV3", out=folder / "out")[1]

    def test_on_and_off(self) -> None:
        folder = self.build()
        self.assertTrue(re.search(r"Soda I\b", self.report(folder, True)))
        off = self.report(folder, False)
        self.assertNotRegex(off, r"Soda I\b")
        self.assertIn("Soda,", off)


if __name__ == "__main__":
    unittest.main()
