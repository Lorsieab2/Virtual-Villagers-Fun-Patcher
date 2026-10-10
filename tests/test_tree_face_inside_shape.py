"""Every portrait's face inside its own shape, and its words never past its frame (the owner, 2026-10-09: a
paw's face sat in the gap between its toes and its pad, a mermaid's tail's on its top edge, a coral's beside
its branches; a beetle's bold "75. Mamba Chuchip" ran 11 pixels past its frame)."""
import copy
import math
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_tree_fixed_face_size import GAME, OWNER_GROUPS, owner_village  # noqa: E402

TURNS = {"plain": {}, "flipped across": {"flip_h": True}, "flipped up": {"flip_v": True}, "turned": {"angle": 30.0}}


def drawn(e: ft.Edits, turn: dict | None = None):
    v = owner_village()
    for p in v.people.values():
        if turn:
            e.entries.setdefault(ft.entry_key(v, p), {}).update(turn)
    lay = ft.layout(v, e)
    return v, lay, ft.scene(lay, GAME, {}).items


def faces(lay, items):
    """Each portrait's face (the round stand-in the tree draws without the game's pictures)."""
    return {i.target[1]: i for i in items if isinstance(i, ft.Shape) and i.kind == "ellipse"
            and i.target and i.target[0] == "person" and i.target[1] in lay.x}


def outside(lay, q, face) -> float:
    """How much of the face lies outside q's outline, as a share of points across it."""
    poly = lay.frame_points(q)
    cx, cy, r = face.x + face.w / 2, face.y + face.h / 2, face.w / 2
    pts = [(cx + r * k / 4 * math.cos(t), cy + r * k / 4 * math.sin(t))
           for k in range(5) for t in (j * math.pi / 8 for j in range(16))]
    return sum(not ft.inside(poly, x, y) for x, y in pts) / len(pts)


def every_shape(sized: bool):
    for shape in ft.PORTRAIT_SHAPES:
        e = ft.Edits(shapes={g: shape for g in ft.GROUPS})
        if sized:                               # the owner's sizes: every group 120 wide
            e.sizes = {g: [120.0, round(120 * ft.NODE_H / ft.natural_width(shape), 1)] for g in ft.GROUPS}
        yield shape, e


class FaceInsideShapeTests(unittest.TestCase):
    def test_every_shape_holds_its_face(self):
        for sized in (False, True):
            for shape, e in every_shape(sized):
                if shape in ft.FACE_KEPT:
                    continue
                for how, turn in TURNS.items():
                    _v, lay, items = drawn(copy.deepcopy(e), turn)
                    for q, face in faces(lay, items).items():
                        with self.subTest(shape=shape, sized=sized, how=how, q=q):
                            self.assertLessEqual(outside(lay, q, face), 0.02)

    def test_a_shape_whose_middle_holds_the_face_keeps_it_there(self):
        for shape in ("rect", "circle", "hexagon", "turtle_h", "monstera", "butterfly"):
            e = ft.Edits(shapes={g: shape for g in ft.GROUPS})
            with mock.patch.object(ft, "face_anchor", lambda *a: (0.0, 0.0, 1.0)):
                _v, lay, items = drawn(copy.deepcopy(e))
                before = {q: (f.x, f.y, f.w) for q, f in faces(lay, items).items()}
            _v, lay, items = drawn(e)
            for q, face in faces(lay, items).items():
                fx, _fy, fw, _fh, _a = lay.frame(q)
                with self.subTest(shape=shape, q=q):
                    self.assertAlmostEqual(face.x + face.w / 2, fx + fw / 2, places=6)
                    self.assertEqual((face.x, face.y, face.w), before[q], "not moved")

    def test_the_owners_tree_is_unchanged(self):
        """The owner's turtle shells, leaves and butterflies: their faces where they always were."""
        _v, lay, items = drawn(ft.Edits(**OWNER_GROUPS))
        for q, face in faces(lay, items).items():
            fx, _fy, fw, _fh, _a = lay.frame(q)
            self.assertAlmostEqual(face.x + face.w / 2, fx + fw / 2, places=6)

    def test_the_paws_face_is_on_its_pad(self):
        _v, lay, items = drawn(ft.Edits(shapes={g: "paw" for g in ft.GROUPS}))
        for q, face in faces(lay, items).items():
            _fx, fy, _fw, fh, _a = lay.frame(q)
            self.assertGreater(face.y, fy + 0.4 * fh, "below the toes")

    def test_with_faces_at_one_size(self):
        for shape in ("paw", "coral", "mermaid_tail_h", "anchor"):
            _v, lay, items = drawn(ft.Edits(fixed_face_size=True, shapes={g: shape for g in ft.GROUPS}))
            for q, face in faces(lay, items).items():
                with self.subTest(shape=shape, q=q):
                    self.assertLessEqual(outside(lay, q, face), 0.02)


class WordWidthTests(unittest.TestCase):
    def test_measured_by_the_fonts_letters(self):
        self.assertGreater(ft.text_width("MAMBA", 11.5, True), len("MAMBA") * 11.5 * 0.58, "capitals wider than the old guess")
        self.assertLess(ft.text_width("iiii", 10), ft.text_width("MMMM", 10))
        self.assertGreater(ft.text_width("MMMM", 10, True), ft.text_width("MMMM", 10))
        self.assertGreater(ft.text_width("Abc", 10, font="Comic Sans MS"), ft.text_width("Abc", 10))

    def test_italic_and_formatted_words_are_measured_as_drawn(self):
        self.assertGreater(ft.text_width("Fatai Awanata and", 10, True, None, True), ft.text_width("Fatai Awanata and", 10, True))
        v = owner_village()
        p = v.people[3]
        line = "Fatai Awanata and Ginger"
        plain = ft.Edits(shapes={g: "monstera" for g in ft.GROUPS}, text_inside=True, text_wrap=60)
        plain.entries[ft.entry_key(v, p)] = {"lines": ["1. Someone", line]}
        styled = copy.deepcopy(plain)
        styled.entries[ft.entry_key(v, p)]["runs"] = [[["1. Someone", {}]], [[line, {"bold": True, "italic": True}]]]

        def size(e):
            return next(i.size for i in ft.scene(ft.layout(v, e), GAME, {}).items
                        if isinstance(i, ft.Text) and i.pid == 3 and i.text == line)
        self.assertLess(size(styled), size(plain), "a bold italic line is wider, so made smaller to fit")

    def test_words_kept_inside_a_shape_stay_a_little_inside_it(self):
        for shape in ("monstera", "heart", "paw", "coral", "star", "hibiscus"):
            e = ft.Edits(shapes={g: shape for g in ft.GROUPS}, text_inside=True)
            lay = ft.layout(owner_village(), e)
            for item in ft.scene(lay, GAME, {}).items:
                if isinstance(item, ft.Text) and item.role in ("names", "portraits") and item.pid in lay.x and item.text:
                    w = ft.text_width(item.text, item.size, item.bold)
                    left = item.x - w / 2
                    m = ft.TEXT_MARGIN - 1.5
                    for at_y in (item.y - item.size * 0.7, item.y):
                        held = [(a, b) for a, b in ft._stretches(lay.frame_points(item.pid), at_y)
                                if a <= left - m and left + w + m <= b]
                        with self.subTest(shape=shape, text=item.text):
                            self.assertTrue(held, "the line a little inside one stretch of the shape")

    def test_words_never_pass_the_frame(self):
        v = owner_village()
        v.people[3].name = "75. Mamba Chuchip"
        for sized in (False, True):
            for shape, e in every_shape(sized):
                lay = ft.layout(v, e)
                for item in ft.scene(lay, GAME, {}).items:
                    if isinstance(item, ft.Text) and item.role in ("names", "portraits") and item.pid in lay.x \
                            and item.text and not item.angle:
                        w = ft.text_width(item.text, item.size, item.bold) / ft.WIDTH_SPARE
                        left = item.x - w / 2 if item.centre else item.x - w if item.end else item.x
                        xs = [x for x, _y in lay.frame_points(item.pid)]
                        with self.subTest(shape=shape, sized=sized, text=item.text):
                            self.assertGreaterEqual(left, min(xs) - 0.5)
                            self.assertLessEqual(left + w, max(xs) + 0.5)


if __name__ == "__main__":
    unittest.main()
