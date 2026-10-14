"""The "continued on page N" labels are laid out as portraits are: each in a place of its own, none on another
label, none on a portrait, with its line still ending at it (the owner, 2026-10-13: many such labels were drawn
on top of one another along the bottom of a page, with long lines to them).  Mothers with several partners
and many neighbouring parents whose children are all on the next page crowd the labels together."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_genealogy import FIRST, Y  # noqa: E402
from test_tree_packed import LAYOUTS  # noqa: E402


def crowded_village(mothers: int, partners: int = 3) -> gen.Village:
    """Founders 1 + 2; their `mothers` daughters (generation 2), each with a lone child's line to the next
    page (the father unknown), and the first of them with three partners of her own -- all on the next
    page -- so four lines leave her a few pixels apart."""
    people: dict[int, gen.Person] = {}
    gens = {1: 1, 2: 1}

    def add(pid, sex, years, father=None, mother=None, **extra):
        people[pid] = gen.Person(pid, f"P{pid}", pid % 8, pid % 8, sex=sex, age=years * Y, alive=True,
                                 father=father, mother=mother, first_seen=FIRST, **extra)
    add(1, "Male", 90, arrived=True, how="Founder")
    add(2, "Female", 89, arrived=True, how="Founder")
    for k in range(mothers):
        add(10 + k, "Female", 50, 1, 2)
        gens[10 + k] = 2
        add(100 + k, "Male", 30, None, 10 + k)
        gens[100 + k] = 3
    for k in range(partners):
        add(200 + k, "Male", 30, arrived=True, how="Custom Island Event")
        gens[200 + k] = 3
        add(300 + k, "Female", 5, 200 + k, 10)
        gens[300 + k] = 3
    v = gen.Village(1, 1, "Crowded Tribe", people)
    gen._generations(v, {FIRST: set(people)})
    for pid, g in gens.items():
        people[pid].generation = g
        v.base_generation[pid] = g
    gen.number_people(v)
    return v


def meets(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class ContinuedLabelsStandApartTests(unittest.TestCase):
    def check(self, v, e, label):
        lay = ft.layout(v, e, 0)
        sc = ft.scene(lay, "Crowded Tribe", {})
        words = [i for i in sc.items if isinstance(i, ft.Text) and i.role == "onward"]
        self.assertEqual(len(words), len([f for f in lay.families if f.onward]), label)
        self.assertGreaterEqual(len(words), 6, label)
        boxes = [ft._extent(w) for w in words]
        for i, a in enumerate(boxes):
            for b in boxes[:i]:
                self.assertFalse(meets(a, b), (label, a, b))        # no label on another
            for q in lay.x:                                          # nor on a portrait
                xs, ys = zip(*lay.frame_points(q))
                self.assertFalse(meets(a, (min(xs), min(ys), max(xs), max(ys))), (label, q, a))
        drawn = ft.lines(lay)
        for f in (f for f in lay.families if f.onward):              # each line still ends at its own label
            ends = [pt for _c, pts, fid, _k in drawn if fid == f.id for pt in pts]
            ex, ey = max(ends, key=lambda pt: (pt[1], pt[0]))
            mine = [w for w in words if w.move == ft.onward_key(v, f)]
            self.assertEqual(len(mine), 1)
            box = ft._extent(mine[0])
            self.assertTrue(box[0] - 8 <= ex <= box[2] + 8, (label, f.id, ex, box))
            self.assertLess(abs(box[1] - ey), 12, (label, f.id))
        self.assertGreater(lay.height, max(b[3] for b in boxes), label)

    def test_every_layout(self):
        v = crowded_village(12)
        for positioning in LAYOUTS:
            with self.subTest(positioning=positioning):
                self.check(v, ft.Edits(page_generations=2, positioning=positioning), positioning)

    def test_retyped_and_enlarged_words(self):
        v = crowded_village(6)
        for positioning in LAYOUTS:
            e = ft.Edits(page_generations=2, positioning=positioning)
            e.words["onward"] = "continued on page {page}, where their children are"
            e.styles["onward"] = ft.clean_style({"scale": 200})
            with self.subTest(positioning=positioning):
                self.check(v, e, positioning)

    def test_uncrowded_labels_stay_centred_under_their_lines(self):
        v = crowded_village(3, partners=0)
        lay = ft.layout(v, ft.Edits(page_generations=2, positioning="dynamic"), 0)
        onward = [f for f in lay.families if f.onward]
        self.assertEqual(len(onward), 3)
        self.assertTrue(all(f.word_dx == 0 for f in onward))


if __name__ == "__main__":
    unittest.main()
