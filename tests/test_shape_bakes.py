"""The Monstera leaf and the feather drawn as the owner straightened them (2026-10-10), and trees saved
before moved on once so they look as they did (vv_family_tree.SHAPE_BAKES, settle_shapes)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402


def _village(n: int = 3) -> gen.Village:
    people = {k: gen.Person(k, f"Villager {k}", k, k, sex="Female" if k % 2 else "Male", alive=True)
              for k in range(1, n + 1)}
    return gen.Village(1, 1, "Test", people)


class ShapeBakesTest(unittest.TestCase):
    def test_owner_leaves_become_straight_and_upright_ones_keep_their_look(self):
        # The owner's 49 leaves (turned 45, flipped across) need nothing; an old upright leaf now needs both.
        self.assertEqual(ft._baked_turn("monstera", 45.0, True, False), (0.0, False))
        self.assertEqual(ft._baked_turn("monstera", 0.0, False, False), (45.0, True))
        # The feather lay upright: an old upright one is turned back up, a quarter round.
        self.assertEqual(ft._baked_turn("feather", 0.0, False, False), (90.0, False))
        self.assertEqual(ft._baked_turn("feather", 270.0, False, False), (0.0, False))

    def test_the_composition_draws_the_same_picture(self):
        # Every old (angle, flips) and its moved-on one draw each point of the traced shape alike.
        def drawn(angle, fh, fv, px, py):           # flip in the box, then turn about its middle
            return ft.turn(-px if fh else px, -py if fv else py, angle)
        for name, (degrees, mirrored) in ft.SHAPE_BAKES.items():
            for old in ((0.0, False, False), (45.0, True, False), (30.0, False, True), (200.0, True, True)):
                new_angle, new_h = ft._baked_turn(name, *old)
                for px, py in ((0.3, -0.2), (-0.1, 0.4)):
                    baked = ft.turn(-px if mirrored else px, py, degrees)      # the shape as it is now traced
                    a, b = drawn(*old, px, py), drawn(new_angle, new_h, False, *baked)
                    self.assertAlmostEqual(a[0], b[0], places=6)
                    self.assertAlmostEqual(a[1], b[1], places=6)

    def test_a_new_tree_draws_them_straightened_and_resets_return_there(self):
        e = ft.Edits()
        self.assertTrue(e.monstera_v2 and e.feather_v2)
        self.assertGreater(ft.ASPECTS["feather"], 2.0)                  # lying across now
        b = ft.BAKED["monstera"]
        self.assertAlmostEqual(ft.natural_height("monstera"), ft.NODE_H * b["new_h"])
        self.assertEqual(ft._baked_size("feather", (ft.NODE_H * 0.442, ft.NODE_H))[0] > ft.NODE_H * 0.9, True)

    def test_an_old_tree_is_moved_on_once(self):
        v = _village()
        old = ft.Edits().to_data()
        for marker in ("monstera_v2", "feather_v2"):
            old.pop(marker)
        old["shapes"] = {**old["shapes"], "Female": "monstera"}
        old["sizes"] = {"Female": [110.0, 114.7]}
        females = [p for p in v.people.values() if ft.group_of(p) == "Female"]
        old["entries"] = {ft.entry_key(v, p): {"angle": 45.0, "flip_h": True} for p in females}
        e = ft.Edits.from_data(old)
        self.assertFalse(e.monstera_v2)
        ft.settle_shapes(e, v)
        self.assertTrue(e.monstera_v2)
        self.assertEqual({k: x for k, x in e.entries.items() if x}, {})          # straight now
        w, h = e.sizes["Female"]
        self.assertAlmostEqual(h / 114.7, b := ft.BAKED["monstera"]["new_h"], places=3)
        # Spaced by the leaf's traced box, as before: the owner's tree keeps its width.
        ow, oh = ft.own_box("monstera", w, h)
        self.assertAlmostEqual(ow, 110.0, delta=0.05)
        self.assertAlmostEqual(oh, 114.7, delta=0.05)
        again = ft.Edits.from_data(e.to_data())                                    # never twice
        ft.settle_shapes(again, v)
        self.assertEqual(again.sizes["Female"], e.sizes["Female"])
        self.assertTrue(math.isfinite(w) and b > 0)
        self.assertFalse(ft.styled({"shapes": old["shapes"]}).monstera_v2)          # a look remembered before
        self.assertTrue(ft.styled({"shapes": old["shapes"]}).feather_v2)            # (no feathers in it)


if __name__ == "__main__":
    unittest.main()
