"""Children follow a villager moved to another generation (the owner, 2026-11-25: "I moved a guy from gen 2 to
gen 1. but his upcoming child I can't change from gen 3 to gen 2" / "the child keeps resetting to gen 3").  When
the player moves a villager (Move to generation, or a portrait dragged into another band), their children --
babies on the way, born ones and grandchildren -- move with them, staying as far below as the records put them,
unless the player moved that child themselves.  Who descends from whom (Kinship) keeps the records' generations."""
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_genealogy import FIRST, Y  # noqa: E402

A, B, C, D, E, F, G, H, P, M, K = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11


def village() -> gen.Village:
    """Founders A+B (I); their son C (II) with D, a founder (I); C+D's son E (III) and a baby on the way F (III);
    E with H (an arrival, II) has G (IV).  A default father P (I) with M (I) has K (II)."""
    people: dict[int, gen.Person] = {}
    gens: dict[int, int] = {}

    def add(pid, sex, years, g, father=None, mother=None, **extra):
        people[pid] = gen.Person(pid, f"P{pid}", pid, pid, sex=sex, age=years * Y, alive=True,
                                 father=father, mother=mother, first_seen=FIRST, **extra)
        gens[pid] = g

    add(A, "Male", 70, 1, arrived=True, how="Founder")
    add(B, "Female", 70, 1, arrived=True, how="Founder")
    add(C, "Male", 45, 2, A, B)
    add(D, "Female", 45, 1, arrived=True, how="Founder", expecting=True)
    add(E, "Male", 25, 3, C, D)
    add(H, "Female", 25, 2, arrived=True, how="Custom Island Event")
    add(G, "Female", 3, 4, E, H)
    add(P, "Male", 60, 1, placeholder=True)
    add(M, "Female", 60, 1, arrived=True, how="Founder")
    add(K, "Male", 30, 2, P, M)
    people[F] = gen.Person(F, "", None, -1, father=C, mother=D, upcoming=True)
    gens[F] = 3
    v = gen.Village(4, 1, "Follow Tribe", people)
    for q, g in gens.items():
        people[q].generation = g
        v.base_generation[q] = g
    gen.number_people(v)
    return v


def key(v, pid) -> str:
    return ft.entry_key(v, v.people[pid])


def shown(v) -> dict[int, int]:
    return {q: p.generation for q, p in v.people.items()}


class ChildrenFollowTests(unittest.TestCase):
    def test_tree_wide_move_takes_children_babies_and_grandchildren(self):
        v = village()
        edits = ft.Edits()
        edits.entries[key(v, C)] = {"generation": 1}
        ft.arrange(v, edits)
        got = shown(v)
        self.assertEqual(got[C], 1)
        self.assertEqual(got[E], 2)          # born child III -> II
        self.assertEqual(got[F], 2)          # baby on the way III -> II
        self.assertEqual(got[G], 3)          # grandchild IV -> III
        self.assertEqual((got[A], got[B], got[D], got[H], got[K]), (1, 1, 1, 2, 2))   # nobody else moves

    def test_a_child_the_player_moved_keeps_their_own(self):
        v = village()
        edits = ft.Edits()
        edits.entries[key(v, C)] = {"generation": 1}
        edits.entries[key(v, E)] = {"generation": 3}
        ft.arrange(v, edits)
        self.assertEqual(v.people[E].generation, 3)
        self.assertEqual(v.people[G].generation, 4)     # the grandchild follows the child's own
        self.assertEqual(v.people[F].generation, 2)     # the baby on the way still follows its father

    def test_moving_the_parent_back_restores_the_children(self):
        v = village()
        edits = ft.Edits()
        edits.entries[key(v, C)] = {"generation": 1}
        ft.arrange(v, edits)
        del edits.entries[key(v, C)]
        ft.arrange(v, edits)
        self.assertEqual(shown(v), dict(v.base_generation))

    def test_page_only_move_follows_on_that_page_only(self):
        v = village()
        edits = ft.Edits()
        edits.pages = [3]                               # pages I-III and III-IV
        ft.arrange(v, edits)
        self.assertEqual(ft.page_spans(edits, v), [(1, 3), (3, 4)])
        pk = str(ft.page_key(edits, v, 0))
        edits.page_edits = {pk: {"entries": {key(v, C): {"generation": 1}}}}
        ft.arrange(v, edits)
        self.assertEqual(shown(v), dict(v.base_generation))     # the tree itself is as the records say
        first = ft.page_village(edits, v, 0)
        self.assertEqual((first.people[C].generation, first.people[E].generation, first.people[F].generation),
                         (1, 2, 2))
        self.assertEqual(first.people[G].generation, 4)  # not on this page: a page moves only within its span
        second = ft.page_village(edits, v, 1)
        self.assertEqual((second.people[E].generation, second.people[G].generation), (3, 4))
        lay = ft.layout(v, edits, 0)                     # the page draws them where it puts them
        self.assertEqual(lay.village.people[E].generation, 2)
        self.assertEqual(lay.village.people[F].generation, 2)

    def test_generation_without_own_is_where_the_parents_take_them(self):
        v = village()
        edits = ft.Edits()
        pk = str(ft.page_key(edits, v, 0))
        edits.page_edits = {pk: {"entries": {key(v, C): {"generation": 1}}}}
        ft.arrange(v, edits)
        # Moving E to II is no edit (they are there anyway); to III (the records') is their own, and holds.
        self.assertEqual(ft.generation_without_own(edits, v, 0, v.people[E]), 2)
        self.assertEqual(ft.generation_without_own(edits, v, 0, v.people[C]), 2)
        edits.page_edits[pk]["entries"][key(v, E)] = {"generation": 3}
        self.assertEqual(ft.generation_without_own(edits, v, 0, v.people[E]), 2)
        page = ft.page_village(edits, v, 0)
        self.assertEqual((page.people[E].generation, page.people[G].generation), (3, 4))

    def test_kinship_keeps_the_records(self):
        v = village()
        before = gen.Kinship(v)
        pairs = [(C, E), (C, F), (A, G), (E, G), (C, G)]
        want = [before.relatedness(a, b) for a, b in pairs]
        edits = ft.Edits()
        edits.entries[key(v, C)] = {"generation": 1}
        ft.arrange(v, edits)
        after = gen.Kinship(v)
        self.assertEqual([after.relatedness(a, b) for a, b in pairs], want)
        self.assertEqual(after.relatedness(C, E), Fraction(1, 2))
        self.assertEqual(v.base_generation[E], 3)

    def test_a_default_father_moved_moves_nobody(self):
        v = village()
        edits = ft.Edits()
        edits.entries[key(v, P)] = {"generation": 3}
        ft.arrange(v, edits)
        self.assertEqual(v.people[P].generation, 3)
        self.assertEqual(v.people[K].generation, 2)     # a default father is nobody's parent here
        self.assertEqual(v.people[M].generation, 1)


if __name__ == "__main__":
    unittest.main()
