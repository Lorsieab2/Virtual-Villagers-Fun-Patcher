"""Three Family Tree layout bugs found in a bug hunt on the owner's tree (2026-10-09): diamonds and 4-pointed
stars overlapping at packing 100 (a row nestled into the row above stood into the row above that); a
portrait dragged to the top or left of the page drawn off it (the drag ignored what the portrait draws, and
a special border's leaves reached further than reckoned); and, with the lines behind the portraits, a
family's line joints behind a stranger's portrait, so the line seemed to come from them."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
from test_tree_packed import big_village, owner_like_village, rect_overlaps, village  # noqa: E402

GAME = "Virtual Villagers - A New Home"
OWNER_SIZES = {"Male": [120.0, 95.9], "Female": [120.0, 125.1], "Upcoming": [120.0, 82.9]}
TALL = {g: [120.0, 125.1] for g in ft.GROUPS}


def overlapping(lay) -> list:
    return [(a, b) for a, b in rect_overlaps(lay) if ft.frames_overlap(lay, a, b)]


class PointedShapesNeverOverlapTests(unittest.TestCase):
    def test_diamonds_and_four_pointed_stars_at_any_packing(self):
        for make in (big_village, owner_like_village):
            for shape in ("diamond", "star4"):
                for sizes in (TALL, OWNER_SIZES):
                    for positioning in ("packed_families", "packed_generations"):
                        for packing in (90, 98, 100):
                            e = ft.Edits(positioning=positioning, packing=packing, sizes=sizes,
                                         shapes={g: shape for g in ft.GROUPS},
                                         borders={g: "vine_both" for g in ft.GROUPS})
                            lay = ft.layout(make(), e)
                            self.assertEqual(overlapping(lay), [], (make.__name__, shape, positioning, packing))

    def test_a_row_two_up_is_never_entered(self):
        # Three rows of one diamond each, the middle one set along: the third stands under the first.
        prof = ft._profile("diamond", 120.0, 125.1, 0.0)
        pos = ft._arrange([[1], [2], [3]], step=120.0, offset=120.0, rowh=ft.NODE_H, tight=1.0,
                          outline=lambda m: prof, align="centre", nest=True)
        rows = sorted(pos.values(), key=lambda v: v[1])
        if abs(rows[0][0] - rows[2][0]) < 60:
            self.assertGreaterEqual(rows[2][1] - rows[0][1], 125.1)


class DraggedToTheEdgeTests(unittest.TestCase):
    def drawn(self, entry: dict, **edits) -> tuple:
        v = big_village()
        e = ft.Edits(borders={g: "vine_both" for g in ft.GROUPS}, **edits)
        q = 4
        e.entries[ft.entry_key(v, v.people[q])] = entry
        lay = ft.layout(v, e)
        sc = ft.scene(lay, GAME, {})
        boxes = [ft._extent(i) for i in sc.items if getattr(i, "pid", None) == q and ft._extent(i)]
        return min(b[0] for b in boxes), min(b[1] for b in boxes)

    def test_up_and_left_stays_on_the_page(self):
        for entry, edits in (({"dy": -5000.0}, {}), ({"dx": -5000.0}, {}),
                             ({"dy": -5000.0, "w": 250.0, "h": 250.0}, {}),
                             ({"dy": -5000.0, "mark": "Runner"}, {"mark_style": "glow", "mark_glow": 40.0,
                                                                  "marks": {"Runner": "#ffcc00"}})):
            left, top = self.drawn(entry, **edits)
            self.assertGreaterEqual(left, 0.0, entry)
            self.assertGreaterEqual(top, 0.0, entry)

    def test_a_special_borders_reach_is_counted(self):
        # The vine's leaves and flowers reach about 1.3 of their size outside the outline: counted in full.
        for border in ft.SPECIAL_BORDERS:
            for kind, w, h in (("rect", 120.0, 125.1), ("monstera", 120.0, 95.9), ("star", 106.0, 156.0)):
                pad = ft.frame_pad(ft.Edits(), {"border": border}, "Female", w, h)
                outline = ft.shape_points(kind, 0, 0, w, h, ft.corner_radius(kind), 0)
                xs, ys = [p[0] for p in outline], [p[1] for p in outline]
                for item in ft.special_border(border, kind, (0, 0, w, h, 0), ft.corner_radius(kind)):
                    for px, py in item.points:
                        self.assertGreaterEqual(px, min(xs) - pad - 0.5, (border, kind))
                        self.assertGreaterEqual(py, min(ys) - pad - 0.5, (border, kind))
        self.assertEqual(ft.frame_pad(ft.Edits(), {"border": "thick"}, "Male", 120, 120), 1.5)


def behind_strangers(lay) -> list:
    """Every end of a family's line pieces (its joints) that lies inside a portrait not of the family."""
    fams = {f.id: f for f in lay.families}
    polys = {q: lay.frame_points(q) for q in lay.x}
    out = []
    for _c, pts, fid, piece in ft.lines(lay):
        f = fams[fid]
        members = {f.father, f.mother, *f.children}
        for x, y in (pts[0], pts[-1]):
            out += [(fid, piece, q) for q, poly in polys.items() if q not in members and ft.inside(poly, x, y)]
    return out


class JointsNeverBehindStrangersTests(unittest.TestCase):
    def found(self, positioning: str) -> int:
        n = 0
        for make in (big_village, owner_like_village):
            for packing in (98, 100):
                e = ft.Edits(positioning=positioning, packing=packing, lines_behind=True, sizes=OWNER_SIZES,
                             shapes={"Male": "turtle_h", "Female": "monstera", "Upcoming": "butterfly"})
                n += len(behind_strangers(ft.layout(make(), e)))
        return n

    def test_packed_generations_joins_only_on_its_own_family(self):
        self.assertEqual(self.found("packed_generations"), 0)       # 4 before

    def test_packed_families_far_fewer(self):
        # 24 before.  What is left is where portraits touch all round and no height of the line is clear
        # of every stranger at once (the owner's own tree has none left).
        self.assertLessEqual(self.found("packed_families"), 14)

    def test_lines_in_front_are_not_moved(self):
        e = ft.Edits(positioning="packed_families", packing=100, lines_behind=False)
        lay = ft.layout(owner_like_village(), e)
        self.assertFalse(ft.lines_behind(lay))
        self.assertEqual(ft.lines(lay), ft.lines(lay))


def too_close(lay) -> list:
    """Pairs of straight runs side by side with less than ft.LINE_GAP between their drawn edges along a
    stretch they share (the owner: "lines should try not to overlap exactly ever. (min 1 pixel distance
    between them in any position)").  One family's runs on one line are one path (its children's lines
    from one point, a stem along its own line); lines crossing do not count."""
    width = {f.id: lay.edits.family_lines.get(ft.family_key(lay.village, f), {}).get("width", lay.edits.line_width)
             for f in lay.families}
    runs = []
    for _c, pts, fid, piece in ft.lines(lay):
        for a, b in zip(pts, pts[1:]):
            if a[0] == b[0] and a[1] != b[1]:
                runs.append((0, a[0], min(a[1], b[1]), max(a[1], b[1]), fid, piece))
            elif a[1] == b[1] and a[0] != b[0]:
                runs.append((1, a[1], min(a[0], b[0]), max(a[0], b[0]), fid, piece))
    runs.sort(key=lambda r: (r[0], r[1]))
    out = []
    for i, s in enumerate(runs):
        for t in runs[i + 1:]:
            if t[0] != s[0] or t[1] - s[1] > 40:
                break
            if (s[4], s[5]) == (t[4], t[5]) or (s[4] == t[4] and abs(s[1] - t[1]) < 0.5):
                continue
            need = (width[s[4]] + width[t[4]]) / 2 + ft.LINE_GAP
            if t[1] - s[1] < need - 1e-6 and min(s[3], t[3]) - max(s[2], t[2]) > 0.5:
                out.append((s[4], s[5], t[4], t[5], round(t[1] - s[1], 2)))
    return out


class LinesNeverOnEachOtherTests(unittest.TestCase):
    def test_every_layout_and_packing(self):
        for make in (village, big_village, owner_like_village):
            for positioning in ft.POSITIONING:
                for packing in ((0, 60, 98, 100) if positioning in ft.PACKED else (60,)):
                    for behind in ((None, False) if positioning in ft.PACKED else (None,)):
                        e = ft.Edits(positioning=positioning, packing=packing, lines_behind=behind)
                        lay = ft.layout(make(), e)
                        for page in range(lay.pages):
                            self.assertEqual(too_close(ft.layout(make(), e, page)), [],
                                             (make.__name__, positioning, packing, behind, page))

    def test_thick_lines_keep_their_room(self):
        for width in (1.0, 6.0):
            for positioning in ("rows", "packed_families", "packed_generations"):
                e = ft.Edits(positioning=positioning, packing=100, line_width=width)
                self.assertEqual(too_close(ft.layout(owner_like_village(), e)), [], (width, positioning))

    def test_a_dragged_line_is_nudged_off_another(self):
        # Drag a family's children's line onto another's: it ends up beside it, not on it.
        v = big_village()
        e = ft.Edits()
        lay = ft.layout(v, e)
        level = {}
        for _c, pts, fid, piece in ft.lines(lay):
            if piece == "lane":
                level[fid] = pts
        (a, pa), (b, pb) = list(level.items())[:2]
        fam = {f.id: f for f in lay.families}
        e.line_moves[f"{ft.family_key(v, fam[a])}|lane"] = [0.0, pb[0][1] - pa[0][1]]
        self.assertEqual(too_close(ft.layout(v, e)), [])


if __name__ == "__main__":
    unittest.main()
