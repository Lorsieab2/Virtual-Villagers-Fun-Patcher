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


def _turns(e: ft.Edits) -> dict:
    return {k: {f: x[f] for f in ("angle", "flip_h", "flip_v") if f in x} for k, x in e.entries.items()
            if any(f in x for f in ("angle", "flip_h", "flip_v"))}


class NewPortraitsAreStraightTest(unittest.TestCase):
    """The owner (2026-10-10): "make sure the monstera orientation fix is in there!  Newly generated ones are
    still in the wrong orientation."  A portrait with no turn or flip of its own is drawn as the shape now is
    (straight up; the feather lying across), whichever way it came to have none, and never turned twice."""

    def old_tree(self, v, turned, shape="monstera") -> dict:
        old = ft.Edits().to_data()
        for marker in ("monstera_v2", "feather_v2", "bakes_v3"):
            old.pop(marker)
        old["shapes"] = {**old["shapes"], "Female": shape}
        old["entries"] = {ft.entry_key(v, v.people[k]): {"angle": 45.0, "flip_h": True} for k in turned}
        return old

    def test_moving_on_an_old_tree_leaves_new_villagers_straight(self):
        v = _village(7)                     # females 1, 3, 5, 7; the player turned 1 and 3 only
        e = ft.Edits.from_data(self.old_tree(v, (1, 3)))
        ft.layout(v, e)
        self.assertEqual(_turns(e), {})     # the chosen look straight now; 5 and 7 never turned to the old look
        self.assertTrue(e.monstera_v2 and e.bakes_v3)
        again = ft.Edits.from_data(e.to_data())
        ft.layout(v, again)
        self.assertEqual(again.to_data(), e.to_data())      # never twice

    def test_a_tree_the_earlier_moving_on_turned_back_is_put_right(self):
        v = _village(9)
        data = ft.Edits().to_data()
        data.pop("bakes_v3")                # moved on (v2) by the build before this fix
        data["shapes"] = {**data["shapes"], "Female": "monstera", "Male": "feather"}
        key = {k: ft.entry_key(v, v.people[k]) for k in v.people}
        data["entries"] = {key[5]: {"angle": 45.0, "flip_h": True},      # given the old look: a new villager
                           key[7]: {"angle": 45.0, "flip_h": True, "w": 90.0},
                           key[9]: {"angle": 30.0},                     # the player's own turn: kept
                           key[2]: {"angle": 90.0},                     # a feather turned to the old look
                           key[4]: {"angle": 45.0, "flip_h": True},     # a feather the player turned: kept
                           key[6]: {"shape": "heart", "angle": 45.0, "flip_h": True}}    # not a turned shape
        e = ft.Edits.from_data(data)
        self.assertFalse(e.bakes_v3)
        ft.layout(v, e)
        self.assertTrue(e.bakes_v3)
        self.assertEqual(_turns(e), {key[9]: {"angle": 30.0}, key[4]: {"angle": 45.0, "flip_h": True},
                                     key[6]: {"angle": 45.0, "flip_h": True}})
        self.assertEqual(e.entries[key[7]], {"w": 90.0})
        self.assertNotIn(key[5], e.entries)
        again = ft.Edits.from_data(e.to_data())
        ft.layout(v, again)
        self.assertEqual(again.entries, e.entries)          # never twice

    def test_a_new_tree_and_reset_everything_draw_them_straight(self):
        v = _village(5)
        for look in (None, {"shapes": {"Female": "monstera", "Male": "feather"}},          # remembered before
                     {"shapes": {"Female": "monstera"}, "monstera_v2": True}):
            e = ft.styled(look)
            ft.layout(v, e)
            self.assertEqual(_turns(e), {}, look)

    def test_a_new_villager_after_an_update_and_resets_and_shape_changes(self):
        v = _village(5)
        e = ft.Edits.from_data(self.old_tree(v, (1, 3)))
        ft.layout(v, e)
        # A villager born since (F5, Update Family Tree): no entry, drawn straight.
        v.people[11] = gen.Person(11, "Villager 11", 11, 11, sex="Female", alive=True)
        ft.layout(v, e)
        self.assertNotIn(ft.entry_key(v, v.people[11]), e.entries)
        self.assertEqual(_turns(e), {})
        # Reset Portrait Shapes takes each portrait's own shape, size, turn and flips away (the window's
        # _set_entry(p, shape=None, ..., angle=None, flip_h=None, flip_v=None)): nothing turns them back.
        key = ft.entry_key(v, v.people[2])
        e.entries[key] = {"shape": "feather"}               # picked from the shape list: no turn of its own
        e.shapes["Male"] = "monstera"                       # a group's shape changed
        ft.layout(v, e)
        self.assertEqual(_turns(e), {})
        self.assertEqual(ft.shape_of(e, v, v.people[2]), "feather")
        self.assertEqual(ft.shape_of(e, v, v.people[4]), "monstera")
        # Reset Everything: the tree as a new one opens.
        fresh = ft.styled({"shapes": dict(e.shapes)})
        ft.layout(v, fresh)
        self.assertEqual(_turns(fresh), {})


if __name__ == "__main__":
    unittest.main()
