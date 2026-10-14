"""A family's line to a later page starts on its parent's portrait, however many families that parent has."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import vv_family_tree as ft  # noqa: E402


def test_many_lines_from_one_parent_all_leave_the_portrait():
    centre, reach = 1000.0, ft.NODE_W / 2 - 16
    got = ft._spread_drops([centre], 40, centre, reach)
    assert len(got) == 40
    assert all(abs(p - centre) <= reach + 1e-6 for p in got)


def test_few_lines_keep_clear_of_the_taken_places():
    got = ft._spread_drops([1000.0], 3, 1000.0, 37.0)
    assert all(abs(p - 1000.0) >= 1.5 for p in got)


@pytest.mark.skipif(not os.environ.get("VVFP_KAL_TREE"), reason="needs a copy of a large village (VVFP_KAL_TREE=<dir>)")
def test_every_onward_line_top_is_on_its_parent():
    import json
    import vv_genealogy as gen
    d = Path(os.environ["VVFP_KAL_TREE"])
    v = gen.load_village(d / "save", 1, 1)
    e = ft.Edits.from_data(json.load(open(d / "tree.vvtree", encoding="utf-8-sig"))["edits"])
    for pg in range(len(ft.page_spans(e, v))):
        lay = ft.layout(v, e, pg)
        frames = ft._frames(lay)
        for f in lay.families:
            if not f.onward:
                continue
            for q in (f.father, f.mother):
                if q in frames and q in f.drops:
                    x0, _y0, x1, _y1, _p = frames[q]
                    assert x0 - 1 <= f.drops[q] <= x1 + 1
