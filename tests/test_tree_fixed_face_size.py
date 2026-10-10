"""Faces and words keep one size, whatever the portrait's shape and size (the owner, 2026-10-09: every group
120 wide -- the females' Monstera leaves 120 x 125.1, the males' turtle shells on their sides 120 x 95.9,
the babies' butterflies 120 x 82.9 -- and the males' faces and words came out a quarter smaller than the
females')."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
from test_tree_packed import LAYOUTS, big_village, off_page  # noqa: E402

GAME = "Virtual Villagers - A New Home"
OWNER_GROUPS = dict(shapes={"Male": "turtle_h", "Female": "monstera", "Upcoming": "butterfly"},
                    sizes={"Male": [120.0, 95.9], "Female": [120.0, 125.1], "Upcoming": [120.0, 82.9]},
                    monstera_v2=False)     # saved before the leaf was drawn turned: moved on, as the owner's
MALE, FEMALE, BABY = 3, 4, 30


def owner_village() -> gen.Village:
    """big_village with a baby on the way to 3 and 8."""
    v = big_village()
    v.people[BABY] = gen.Person(BABY, "Upcoming child", -1, -1, upcoming=True, mother=8, father=3, generation=3)
    v.base_generation[BABY] = 3
    return v


def sizes(e: ft.Edits) -> dict:
    """Each of the three portraits' (face width, name size), as the scene draws them."""
    lay = ft.layout(owner_village(), e)
    items = ft.scene(lay, GAME, {}).items
    out = {}
    for q in (MALE, FEMALE, BABY):
        faces = [i for i in items if isinstance(i, ft.Shape) and i.kind == "ellipse" and i.target == ("person", q)]
        names = [i for i in items if isinstance(i, ft.Text) and i.pid == q and i.role == "names"]
        out[q] = (round(faces[-1].w, 2) if faces else None, round(names[0].size, 2))
    return out, lay


class FixedFaceSizeTests(unittest.TestCase):
    def test_the_owners_groups_draw_one_size(self):
        got, lay = sizes(ft.Edits(fixed_face_size=True, **OWNER_GROUPS))
        self.assertEqual(got[MALE], got[FEMALE], "the turtle shell's face and words as the leaf's")
        self.assertEqual(got[BABY][1], 12.0, "the butterfly's words at their own size")
        for q in (MALE, FEMALE):                # the face inside the frame
            fx, fy, fw, fh, _a = lay.frame(q)
            face = next(i for i in reversed(ft.scene(lay, GAME, {}).items)
                        if isinstance(i, ft.Shape) and i.kind == "ellipse" and i.target == ("person", q))
            self.assertTrue(fy <= face.y and face.y + face.h <= fy + fh, q)

    def test_unticked_nothing_changes(self):
        before, _lay = sizes(ft.Edits(**OWNER_GROUPS))
        self.assertLess(before[MALE][0], before[FEMALE][0], "as the owner saw: the males' faces smaller")
        self.assertEqual(before, sizes(ft.Edits(fixed_face_size=False, **OWNER_GROUPS))[0])
        self.assertAlmostEqual(before[MALE][0] / before[FEMALE][0], 95.9 / 156 / (120 / (156 * round(ft.BAKED["monstera"]["old_w"], 3))),  # the leaf as it was
                               delta=0.02)

    def test_kept_inside_the_shape_the_words_still_fit(self):
        got, lay = sizes(ft.Edits(fixed_face_size=True, text_inside=True, **OWNER_GROUPS))
        self.assertEqual(got[FEMALE], sizes(ft.Edits(fixed_face_size=True, **OWNER_GROUPS))[0][FEMALE])
        self.assertLess(got[MALE][0], got[FEMALE][0], "a short shell holds a smaller face and words")
        self.assertGreater(got[MALE][1], 6.0, "but never all but unreadably small")

    def test_a_frame_too_small_for_the_face_shrinks_it_to_fit(self):
        e = ft.Edits(fixed_face_size=True, shapes={"Male": "rect", "Female": "rect", "Upcoming": "rect"},
                     sizes={"Male": [40.0, 40.0], "Female": [120.0, 156.0], "Upcoming": [120.0, 156.0]})
        lay = ft.layout(owner_village(), e)
        fx, fy, fw, fh, _a = lay.frame(MALE)
        face = next(i for i in reversed(ft.scene(lay, GAME, {}).items)
                    if isinstance(i, ft.Shape) and i.kind == "ellipse" and i.target == ("person", MALE))
        self.assertTrue(fx <= face.x and face.x + face.w <= fx + fw and fy <= face.y and face.y + face.h <= fy + fh)

    def test_by_group(self):
        e = ft.Edits(group_opts={"Male": {"fixed_face_size": True}}, **OWNER_GROUPS)
        got, _lay = sizes(e)
        plain, _ = sizes(ft.Edits(**OWNER_GROUPS))
        self.assertEqual(got[FEMALE], plain[FEMALE], "the females as the tree's own")
        self.assertGreater(got[MALE][0], plain[MALE][0], "the males at one size")
        back = ft.Edits._from_data(e.to_data())
        self.assertEqual(back.group_opts, {"Male": {"fixed_face_size": True}})
        self.assertEqual(ft.clean_group_opts({"Male": {"fixed_face_size": "yes"}}), {})

    def test_saved_and_remembered(self):
        self.assertFalse(ft.Edits().fixed_face_size, "existing trees do not change")
        self.assertTrue(ft.Edits._from_data(ft.Edits(fixed_face_size=True).to_data()).fixed_face_size)
        self.assertFalse(ft.Edits._from_data({"fixed_face_size": "yes"}).fixed_face_size)
        self.assertIn("fixed_face_size", ft.STYLE_KEYS)
        self.assertIn("fixed_face_size", ft.GROUP_FIELDS)

    def test_the_page_and_packing_hold_the_words(self):
        # Words run on below a short frame: the page holds them, and packed tight nothing overlaps them.
        for positioning in LAYOUTS:
            for packing in (60, 100):
                e = ft.Edits(positioning=positioning, packing=packing, fixed_face_size=True, **OWNER_GROUPS)
                lay = ft.layout(owner_village(), e)
                self.assertEqual(off_page(lay), [], (positioning, packing))
                texts = [i for i in ft.scene(lay, GAME, {}).items if isinstance(i, ft.Text) and i.pid in lay.x
                         and i.role in ("names", "portraits")]
                frames = {q: lay.frame(q) for q in lay.x}
                for t in texts:
                    for q, (fx, fy, fw, fh, _a) in frames.items():
                        if q != t.pid:
                            self.assertFalse(fx + 4 < t.x < fx + fw - 4 and fy + 4 < t.y < fy + fh - 4,
                                             (positioning, packing, t.pid, q, t.text))

    def test_the_windows_setting_undoes_and_goes_by_group(self):
        from test_tree_group_settings import _Editor
        import vv_genealogy_window as gw
        ed = _Editor()
        ed._change(fixed_face_size=True)
        self.assertTrue(ed.edits.fixed_face_size)
        ed._undo()
        self.assertFalse(ed.edits.fixed_face_size)
        ed._redo()
        self.assertTrue(ed.edits.fixed_face_size)
        ed._change(fixed_face_size=False)
        ed.scope_var.set(ft.GROUPS["Male"])            # "Settings for:" Males
        ed._change(fixed_face_size=True)
        self.assertFalse(ed.edits.fixed_face_size)
        self.assertEqual(ed.edits.group_opts, {"Male": {"fixed_face_size": True}})
        self.assertTrue(ed._view().fixed_face_size)
        ed._clear_group("Male", ("fixed_face_size",))   # its Reset, with Males picked
        self.assertEqual(ed.edits.group_opts, {})
        ed._undo()
        self.assertEqual(ed.edits.group_opts, {"Male": {"fixed_face_size": True}})
        self.assertTrue(gw.EVERYONE)

    def test_the_window_offers_it(self):
        source = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        for text in ("Faces and words keep one size, whatever the portrait's shape and size",
                     'self._reset_button(fixed_row, "fixed_face_size")', "self.fixed_face_var.set(e.fixed_face_size)",
                     "fixed_face_size=bool(self.fixed_face_var.get())"):
            self.assertIn(text, source)


if __name__ == "__main__":
    unittest.main()
