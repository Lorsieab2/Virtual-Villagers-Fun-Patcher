"""The Family Tree never makes a blank page (the owner, 2026-11-22: "why are there 9 pages with blank ones????
FIX THAT CRAP IN ALL 5 GAMES NOW").  A New Believers tree whose generation numbers jumped from VII to XLI gave
nine pages: page_spans cut the tree every six generation *numbers*, so the pages for VIII to XL showed nobody.
The pages are made of the generations someone is in, so every page -- the window's, its picture export and the
genealogy report's pictures -- shows portraits, a generation with nobody in it never takes a row, and a
generation the player hid altogether takes no page either.  In all five games, with a wide generation and a tall tree."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_genealogy import FIRST, Y  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
GAPPED = [1, 2, 3, 4, 5, 6, 7, 41, 42, 43, 44, 45]      # the owner's tree: VII, then XLI
WIDE = 44                                               # a generation of many children


def chain_village(game: int, numbers: list[int], wide: int = 0) -> gen.Village:
    """A line of couples, one per generation in `numbers` (each husband the son of the couple before, each
    wife an arrival), the generations given those numbers as the records would; the generation `wide`
    has 30 more children of the couple before."""
    people: dict[int, gen.Person] = {}
    gens: dict[int, int] = {}

    def add(pid, sex, years, g, father=None, mother=None, **extra):
        people[pid] = gen.Person(pid, f"P{pid}", pid % 8, pid % 8, sex=sex, age=years * Y, alive=True,
                                 father=father, mother=mother, first_seen=FIRST, **extra)
        gens[pid] = g

    father = mother = None
    years = 5 * len(numbers) + 20
    pid = 1
    for g in numbers:
        add(pid, "Male", years, g, father, mother, **({} if father else {"arrived": True, "how": "Founder"}))
        add(pid + 1, "Female", years, g, arrived=True, how="Custom Island Event")
        if g == wide:
            for k in range(30):
                add(1000 + k, "Female" if k % 2 else "Male", max(1, years - 1), g, father, mother)
        father, mother = pid, pid + 1
        pid += 2
        years -= 5
    v = gen.Village(game, 1, "Paging Tribe", people)
    for q, g in gens.items():
        people[q].generation = g
        v.base_generation[q] = g
    gen.number_people(v)
    return v


def page_generations(lay) -> set[int]:
    return {lay.village.people[q].generation for q in lay.x}


class NoBlankPagesTests(unittest.TestCase):
    def assert_no_blank_page(self, v, edits) -> list:
        ft.arrange(v, edits)
        spans = ft.page_spans(edits, v)
        shown = set(ft.shown_generations(edits, v))
        for k, (lo, hi) in enumerate(spans):
            lay = ft.layout(v, edits, k)
            self.assertTrue(lay.x, f"page {k + 1} ({lo}-{hi}) is blank")
            self.assertEqual(lay.pages, len(spans))
            # Every generation the page spans that has someone is on it; none of nobody has a row.
            self.assertEqual(page_generations(lay) | {lay.village.people[q].generation for q in lay.others},
                             {g for g in shown if lo <= g <= hi})
            self.assertEqual(set(lay.tops), page_generations(lay) | {lay.village.people[q].generation
                                                                     for q in lay.others})
            self.assertLessEqual(len([g for g in shown if lo <= g <= hi]), edits.page_generations)
            sc = ft.scene(lay, "Test", {})
            self.assertGreater(sc.height, 0)
        return spans

    def test_a_generation_gap_makes_no_blank_pages_in_every_game(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = chain_village(game, GAPPED, wide=WIDE)
                spans = self.assert_no_blank_page(v, ft.Edits())
                # Twelve generations at six a page, each page starting with the last one's: three pages,
                # not the nine (1-6, 6-11, ... 36-41, 41-45) the numbers between made.
                self.assertEqual(spans, [(1, 6), (6, 44), (44, 45)])

    def test_the_same_tree_numbered_without_the_gap_gives_the_same_pages(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = chain_village(game, list(range(1, 13)), wide=11)
                self.assertEqual(self.assert_no_blank_page(v, ft.Edits()), [(1, 6), (6, 11), (11, 12)])

    def test_a_tall_tree_with_gaps_and_ten_a_page(self) -> None:
        numbers = [1, 2, 9, 10, 11, 30, 31, 32, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61]
        for game in GAMES:
            with self.subTest(game=game):
                v = chain_village(game, numbers, wide=53)
                spans = self.assert_no_blank_page(v, ft.Edits(page_generations=10))
                self.assertEqual(spans, [(1, 51), (51, 60), (60, 61)])

    def test_the_players_page_breaks_still_count_and_one_at_a_gap_makes_no_page(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = chain_village(game, GAPPED)
                self.assertEqual(self.assert_no_blank_page(v, ft.Edits(pages=[4])), [(1, 4), (4, 42), (42, 45)])
                self.assertEqual(ft.page_spans(ft.Edits(pages=[20]), v), [(1, 6), (6, 44), (44, 45)])

    def test_a_generation_the_player_hid_altogether_takes_no_page(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                v = chain_village(game, [1, 2, 3, 4, 5, 6, 7])
                edits = ft.Edits()
                for p in v.people.values():
                    if p.generation == 7:
                        edits.entries[ft.entry_key(v, p)] = {"hidden": True}
                self.assertEqual(self.assert_no_blank_page(v, edits), [(1, 6)])

    def test_a_generation_hidden_on_one_page_only_never_moves_the_pages(self) -> None:
        # Codex, PR #844: the page's own hides were laid over the edits before the pages were worked out, so
        # hiding generation VI on page 1 made that page see 1-7, 7-12 while the others saw 1-6, 6-11, 11-12.
        for game in GAMES:
            with self.subTest(game=game):
                v = chain_village(game, list(range(1, 13)))
                edits = ft.Edits()
                ft.arrange(v, edits)
                hide = {ft.entry_key(v, p): {"hidden": True} for p in v.people.values() if p.generation == 6}
                edits.page_edits = {"1": {"entries": hide}}
                tree = [(1, 6), (6, 11), (11, 12)]
                self.assertEqual(ft.page_spans(edits, v), tree)
                for k in range(3):
                    lay = ft.layout(v, edits, k)
                    self.assertEqual((lay.page, lay.pages), (k, 3))
                    self.assertTrue(lay.x)
                    lo, hi = tree[k]
                    self.assertTrue(all(lo <= g <= hi for g in page_generations(lay)), (k, page_generations(lay)))
                self.assertNotIn(6, page_generations(ft.layout(v, edits, 0)))     # hidden on page 1 alone
                self.assertIn(6, page_generations(ft.layout(v, edits, 1)))
                self.assertEqual(ft.page_view(edits, v, 0).tree_spans, tree)
                self.assertNotIn("tree_spans", ft.page_view(edits, v, 0).to_data())

    def test_the_window_refuses_a_page_break_at_a_generation_of_nobody(self) -> None:
        source = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        body = source[source.index("    def _add_page_break("):source.index("    def _remove_page_break(")]
        self.assertIn("ft.shown_generations(self.edits, self.village)", body)


if __name__ == "__main__":
    unittest.main()
