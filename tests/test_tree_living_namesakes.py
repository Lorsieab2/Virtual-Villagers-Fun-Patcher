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

import json
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
        # Each by what tells them apart for good, never by age (Codex, PR #653): neither has the plain key.
        self.assertEqual(ft.entry_key(v, elder), "Tepeu Tamikai|12|5|" + elder.marker)
        self.assertEqual(ft.entry_key(v, boy), "Tepeu Tamikai|12|5|" + boy.marker)
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
                       "The second oldest", q.text, parent_identity=q.identity_of("The second oldest"), group=q.group)
        v = gen.load_village(folder, 3, 1)
        ponui = next(p for p in v.people.values() if p.name == "Ponui Kalama")
        younger = self.tepeus(v)[1]
        self.assertEqual(ponui.father, younger.id, "the player's answer links him")
        self.assertEqual(v.parent_questions, [])

    KID = ("Kid", 20, 21)

    def two_kids(self, extra: list[bytes] = ()) -> Path:
        """Codex, PR #653: two living "Kid" namesakes (120 and 100) both name "Tepeu Tamikai" as their father, and
        both Tepeus (1583 and 1000) were old enough to be either one's."""
        return save(self.folder(), [
            aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
            tepeu(1583, ("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
            tepeu(1000, ("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
            aged(entry(self.KID[0], 0, 37, self.KID[1], self.KID[2], father=TEPEU,
                       mother=("Parai Tokidoki", 7, 7)), 120),
            aged(entry(self.KID[0], 0, 38, self.KID[1], self.KID[2], father=TEPEU,
                       mother=("Parai Tokidoki", 7, 7)), 100),
            *extra,
        ])

    def kids(self, v: gen.Village) -> list:
        return sorted((p for p in v.people.values() if p.key == self.KID), key=lambda p: -(p.age or 0))

    def test_two_namesake_children_keep_an_answer_each(self) -> None:
        self.answer_two_kids()

    def answer_two_kids(self) -> Path:
        folder = self.two_kids()
        v = gen.load_village(folder, 3, 1)
        qs = sorted(v.parent_questions, key=lambda q: q.child_rank)
        self.assertEqual([(q.child, q.child_rank) for q in qs], [(self.KID, 1), (self.KID, 2)])
        self.assertNotEqual(qs[0].text, qs[1].text, "the owner can tell the two children apart")
        self.assertIn("120 game units", qs[0].text)
        self.assertIn("100 game units", qs[1].text)
        for q, answer in zip(qs, ("The oldest", "The second oldest")):
            aq.keep_parent(folder, 3, 1, q.child, q.parent, q.label, ["The oldest", "The second oldest"],
                           answer, q.text, child_rank=q.child_rank, parent_identity=q.identity_of(answer),
                           group=q.group, child_marker=q.child_marker, child_group=q.child_group)
        v = gen.load_village(folder, 3, 1)
        elder, younger = self.tepeus(v)
        older_kid, younger_kid = self.kids(v)
        self.assertEqual((older_kid.father, younger_kid.father), (elder.id, younger.id),
                         "each child keeps their own answer after a reload")
        self.assertEqual(v.parent_questions, [])
        self.assertEqual(len([d for d in aq.decisions.load(folder, 3, 1) if d.get("source") == aq.PARENT_SOURCE]), 2)
        return folder

    def test_a_tie_between_children_holds_only_while_their_group_is_unchanged(self) -> None:
        """The two Kids share their marker (a boy, mother Parai): only their place by age tells them apart, so
        once one of them is gone the other is asked again (Codex, PR #653)."""
        markers = {q.child_marker for q in gen.load_village(self.two_kids(), 3, 1).parent_questions}
        self.assertEqual(len(markers), 1, "(the two Kids share their marker)")
        folder = self.answer_two_kids()
        save(folder, [
            aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
            tepeu(1583, ("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
            tepeu(1000, ("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
            aged(entry(self.KID[0], 0, 38, self.KID[1], self.KID[2], father=TEPEU,
                       mother=("Parai Tokidoki", 7, 7)), 100),
        ])
        v = gen.load_village(folder, 3, 1)
        self.assertIsNone(self.kids(v)[0].father, "which of the two it was is not known any more")
        self.assertEqual(len(v.parent_questions), 1)

    MOTHERS = {140: ("Ana Ke", 8, 8), 120: ("Ana Lu", 9, 9), 100: ("Ana Mo", 10, 10)}

    def three_kids(self, folder: Path, ages=(140, 120, 100)) -> Path:
        """Codex, PR #653: three living "Kid" namesakes, each of their own mother, all naming "Tepeu Tamikai"
        as their father; both Tepeus old enough to be any one's."""
        return save(folder, [
            *(aged(entry(m[0], 1, 5, m[1], m[2]), 900) for m in self.MOTHERS.values()),
            tepeu(1583, ("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
            tepeu(1000, ("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
            *(aged(entry(self.KID[0], 0, 37, self.KID[1], self.KID[2], father=TEPEU, mother=self.MOTHERS[a]), a)
              for a in ages),
        ])

    def kid_fathers(self, folder: Path) -> dict:
        v = gen.load_village(folder, 3, 1)
        return {k.age: (v.people[k.father].age if k.father is not None else None) for k in self.kids(v)}, v

    def test_a_childs_answer_stays_theirs_when_an_older_namesake_child_dies(self) -> None:
        folder = self.three_kids(self.folder())
        v = gen.load_village(folder, 3, 1)
        self.assertEqual(len(v.parent_questions), 3)
        wanted = {140: "The oldest", 120: "The second oldest", 100: "The oldest"}
        for q in v.parent_questions:
            age = v.people[q.child_id].age
            aq.keep_parent(folder, 3, 1, q.child, q.parent, q.label, [t.split(" (")[0] for t in q.texts],
                           wanted[age], q.text, child_rank=q.child_rank, parent_identity=q.identity_of(wanted[age]),
                           group=q.group, child_marker=q.child_marker, child_group=q.child_group)
        fathers, v = self.kid_fathers(folder)
        self.assertEqual(fathers, {140: 1583, 120: 1000, 100: 1583})
        self.assertEqual(v.parent_questions, [])
        # The eldest Kid dies: the 120 one is now "the oldest of that name", and keeps their own answer.
        self.three_kids(folder, (120, 100))
        fathers, v = self.kid_fathers(folder)
        self.assertEqual(fathers, {120: 1000, 100: 1583}, "never the dead child's answer")
        self.assertEqual(v.parent_questions, [])
        # The youngest dies instead (an unrelated child): the others keep theirs.
        self.three_kids(folder, (140, 120))
        fathers, v = self.kid_fathers(folder)
        self.assertEqual(fathers, {140: 1583, 120: 1000})
        self.assertEqual(v.parent_questions, [])

    def test_an_old_answer_without_a_child_rank_still_loads(self) -> None:
        """An answer kept before the child's rank was: it still links a child with no living namesake, and is
        never given to one of two namesake children (they are asked again)."""
        folder = save(self.folder(), [
            aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
            tepeu(1583, ("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
            aged(entry("Ponui Kalama", 0, 37, 10, 17, father=TEPEU, mother=("Parai Tokidoki", 7, 7)), 300),
            tepeu(1000, ("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
        ])
        ponui = ("Ponui Kalama", 10, 17)
        old_entry = {
            "kind": aq.KIND, "village": aq.village_header(folder, 3, 1),
            "field": aq.base_of(aq.PARENT_SOURCE, "Father", (ponui, TEPEU)), "source": aq.PARENT_SOURCE,
            "fact": "Father", "who": [list(ponui), list(TEPEU)], "ordinal": 1, "of": 1, "question": "old",
            "options": ["The oldest", "The second oldest"], "verdict": "The second oldest",
            "label": aq.PARENT_LABEL, "edited": False, "alone": True}
        aq.decisions.record(folder, 3, 1, [old_entry])
        v = gen.load_village(folder, 3, 1)
        p = next(q for q in v.people.values() if q.name == "Ponui Kalama")
        self.assertEqual(p.father, self.tepeus(v)[1].id, "the old answer still links him")
        self.assertEqual(v.parent_questions, [])

        folder = self.two_kids()
        aq.decisions.record(folder, 3, 1, [{
            **old_entry, "village": aq.village_header(folder, 3, 1),
            "field": aq.base_of(aq.PARENT_SOURCE, "Father", (self.KID, TEPEU)),
            "who": [list(self.KID), list(TEPEU)]}])
        v = gen.load_village(folder, 3, 1)
        self.assertEqual([k.father for k in self.kids(v)], [None, None], "which child it was for is not known")
        self.assertEqual(len(v.parent_questions), 2, "both are asked again")

    PARENTS = {1583: (("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
               1200: (("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
               1000: (("Lani Kekoa", 11, 3), ("Mele Pua", 8, 6))}

    def three_tepeus(self, folder: Path, ages=(1583, 1200, 1000)) -> Path:
        """Codex, PR #653: three living Tepeus, each old enough to be Ponui's father, each with their own
        parents."""
        for f in folder.glob("*.ldw"):
            f.unlink()
        return save(folder, [
            aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
            aged(entry("Ponui Kalama", 0, 37, 10, 17, father=TEPEU, mother=("Parai Tokidoki", 7, 7)), 300),
            *(tepeu(age, *self.PARENTS[age]) for age in ages),
        ])

    def ponui(self, v: gen.Village):
        return next(p for p in v.people.values() if p.name == "Ponui Kalama")

    def father_age(self, v: gen.Village):
        p = self.ponui(v)
        return v.people[p.father].age if p.father is not None else None

    def answer(self, folder: Path, words: str, identity: bool = True) -> None:
        q = gen.load_village(folder, 3, 1).parent_questions[0]
        options = [t.split(" (")[0] for t in q.texts]
        aq.keep_parent(folder, 3, 1, q.child, q.parent, q.label, options, words, q.text,
                       parent_identity=q.identity_of(words) if identity else None,
                       group=q.group if identity else None)

    def test_an_answer_stays_with_the_parent_after_an_older_namesake_dies(self) -> None:
        folder = self.three_tepeus(self.folder())
        self.answer(folder, "The second oldest")
        v = gen.load_village(folder, 3, 1)
        self.assertEqual(self.father_age(v), 1200)
        self.assertEqual(v.parent_questions, [])
        # The eldest dies: "The second oldest" would now be the 1000 one; the answer stays with the 1200 one.
        self.three_tepeus(folder, (1200, 1000))
        v = gen.load_village(folder, 3, 1)
        self.assertEqual(self.father_age(v), 1200, "never moved to another villager by the place by age")
        self.assertEqual(v.parent_questions, [])
        # The youngest dies (an unrelated death): still the 1200 one.
        self.three_tepeus(folder, (1583, 1200))
        v = gen.load_village(folder, 3, 1)
        self.assertEqual(self.father_age(v), 1200)
        self.assertEqual(v.parent_questions, [])

    def test_the_chosen_parent_gone_is_asked_again(self) -> None:
        folder = self.three_tepeus(self.folder())
        self.answer(folder, "The second oldest")
        self.three_tepeus(folder, (1583, 1000))
        v = gen.load_village(folder, 3, 1)
        self.assertIsNone(self.ponui(v).father, "the one chosen is gone: nobody else is given the answer")
        self.assertEqual(len(v.parent_questions), 1)

    def test_an_old_rank_only_answer_holds_only_while_the_group_is_as_it_was(self) -> None:
        folder = self.three_tepeus(self.folder())
        self.answer(folder, "The second oldest", identity=False)
        v = gen.load_village(folder, 3, 1)
        self.assertEqual(self.father_age(v), 1200, "the same three: the old answer still holds")
        self.assertEqual(v.parent_questions, [])
        self.three_tepeus(folder, (1200, 1000))
        v = gen.load_village(folder, 3, 1)
        self.assertIsNone(self.ponui(v).father, "the group changed: the old answer is not applied")
        self.assertEqual(len(v.parent_questions), 1)

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


class NamesakesKeepTheirOwnEdits(unittest.TestCase):
    """Codex, PR #653: a namesake's tree edits are kept by what tells them apart for good (sex and recorded
    parents), never by their place by age; nothing is ever given to another villager or deleted."""

    PARENTS = {1583: (("Pichu Tamikai", 14, 18), ("Toga Helaku", 9, 17)),
               1200: (("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17)),
               1000: (("Lani Kekoa", 11, 3), ("Mele Pua", 8, 6))}
    TWINS = (("Oro Kenobi", 12, 9), ("Coral Guedado", 10, 17))

    def setUp(self) -> None:
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def village(self, ages, parents=None) -> gen.Village:
        save(self.dir, [aged(entry("Parai Tokidoki", 1, 5, 7, 7), 900),
                        *(tepeu(a, *(parents or self.PARENTS)[a]) for a in ages)])
        return gen.load_village(self.dir, 3, 1)

    def by_age(self, v: gen.Village) -> dict:
        return {p.age: p for p in v.people.values() if p.key == TEPEU and p.alive}

    def edits(self) -> ft.Edits:
        return ft.Edits.load(ft.Edits.path(self.dir, 3, 1))

    def label(self, v: gen.Village, e: ft.Edits, age: int):
        return e.entries.get(ft.entry_key(v, self.by_age(v)[age]), {}).get("lines")

    def keep(self, v: gen.Village, e: ft.Edits) -> None:
        ft.arrange(v, e)
        path = ft.Edits.path(self.dir, 3, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        e.save(path)

    def reopen(self, ages, parents=None) -> tuple:
        v = self.village(ages, parents)
        e = self.edits()
        ft.arrange(v, e)
        return v, e

    def labelled(self, ages=(1583, 1200, 1000), parents=None) -> None:
        v = self.village(ages, parents)
        e = ft.Edits()
        ft.arrange(v, e)
        for age, p in self.by_age(v).items():
            e.entries[ft.entry_key(v, p)] = {"lines": [f"T{age}"], "hidden": True} if age == 1000 else \
                {"lines": [f"T{age}"]}
        self.keep(v, e)

    def test_an_older_namesakes_death_moves_no_edit(self) -> None:
        self.labelled()
        v, e = self.reopen((1200, 1000))
        self.assertEqual(self.label(v, e, 1200), ["T1200"], "the 1200 one keeps their own label")
        self.assertEqual(self.label(v, e, 1000), ["T1000"])
        self.assertIsNotNone(self.by_age(v)[1200].number, "the 1000 one's deleted flag never moves to the 1200 one")
        self.assertIsNone(self.by_age(v)[1000].number, "and stays the 1000 one's")

    def test_an_unrelated_namesakes_death_leaves_the_others(self) -> None:
        self.labelled()
        v, e = self.reopen((1583, 1200))
        self.assertEqual((self.label(v, e, 1583), self.label(v, e, 1200)), (["T1583"], ["T1200"]))

    def test_the_last_one_left_takes_their_own_edits_back_under_the_plain_key(self) -> None:
        self.labelled()
        v, e = self.reopen((1200,))
        self.assertEqual(ft.entry_key(v, self.by_age(v)[1200]), "Tepeu Tamikai|12|5")
        self.assertEqual(self.label(v, e, 1200), ["T1200"])
        self.assertTrue(any(k.startswith(ft.PARKED) and v_.get("lines") == ["T1583"] for k, v_ in e.entries.items()),
                        "the dead one's label is kept, applied to nobody")

    def test_a_namesake_appearing_leaves_the_first_ones_edits_with_them(self) -> None:
        v = self.village((1583,))
        e = ft.Edits(entries={"Tepeu Tamikai|12|5": {"lines": ["Elder"]}})
        self.keep(v, e)
        v, e = self.reopen((1583, 1200))
        self.assertEqual(self.label(v, e, 1583), ["Elder"])
        self.assertIsNone(self.label(v, e, 1200), "the newcomer never takes them")

    def test_twins_of_one_record_hold_their_edits_only_while_the_group_is_unchanged(self) -> None:
        twins = {1200: self.TWINS, 1000: self.TWINS, 1583: self.PARENTS[1583]}
        self.labelled((1583, 1200, 1000), twins)
        v, e = self.reopen((1583, 1200, 1000), twins)
        self.assertEqual((self.label(v, e, 1200), self.label(v, e, 1000)), (["T1200"], ["T1000"]))
        v, e = self.reopen((1200, 1000), twins)
        self.assertEqual((self.label(v, e, 1200), self.label(v, e, 1000)), (None, None),
                         "the group changed: which twin was which is not known")
        self.assertEqual(sorted(x["lines"][0] for k, x in e.entries.items() if k.startswith(ft.PARKED)),
                         ["T1000", "T1200"], "the twins' edits kept, parked, never deleted")
        self.assertIn(["T1583"], [x.get("lines") for x in e.entries.values()],
                      "the dead one's, kept under their own key")

    def test_old_rank_keys_are_never_given_to_anyone(self) -> None:
        v = self.village((1583, 1200))
        e = ft.Edits(entries={"Tepeu Tamikai|12|5": {"lines": ["Old first"]}, "Tepeu Tamikai|12|5|2": {"lines": ["Old second"]}},
                     person_colours={"Tepeu Tamikai|12|5|2": "#123456"})
        self.keep(v, e)
        v, e = self.reopen((1200,))
        self.assertIsNone(self.label(v, e, 1200), "an earlier build's key by age is never anyone's now")
        self.assertEqual(sorted(x["lines"][0] for k, x in e.entries.items() if k.startswith(ft.PARKED)),
                         ["Old first", "Old second"])
        self.assertIn(ft.PARKED + "Tepeu Tamikai|12|5|2", e.person_colours)

    def test_an_edits_file_with_no_namesakes_is_unchanged(self) -> None:
        v = hand_village()
        e = ft.Edits(entries={ft.entry_key(v, p): {"lines": [p.name]} for p in v.people.values()})
        before = json.dumps(e.entries, sort_keys=True)
        ft.arrange(v, e)
        self.assertEqual(json.dumps(e.entries, sort_keys=True), before)
        self.assertTrue(all(ft.entry_key(v, p) == f"{p.name}|{p.head}|{p.body}" for p in v.people.values()
                            if not p.upcoming))


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
