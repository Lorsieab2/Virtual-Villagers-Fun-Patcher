"""VV3's "Change Appearance for All" matches the other four games.

The owner reported this window as the one that still did not match. It did not:
VV1, VV2, VV4 and VV5 all lay it out as two columns -- the Male and Female
panels on the left, and a right-hand column at x=382 carrying three groups,
Village-wide Heads, Village-wide Bodies and Village-wide Single Mask Color,
with the Mask Distribution box full width along the bottom. VV3 had a single
368-wide column, no Heads or Bodies override at all, and its Single Mask Color
box in the wrong place.

The control ids could not simply be copied across. The other games number
Village-wide Heads 3220..3226 and Bodies 3240..3241, but 3220..3229 is already
VV3's FEMALE panel, so VV3 uses a 3400 block instead. That is the one
deliberate difference and it is asserted here so nobody "fixes" it back into a
collision.

Two further things this pins:

  * The hair-colour buckets are generated from the head sheets rather than
    hand-written, so "All Black Hair" cannot silently drift from the artwork.
  * The mask radios remain ONE exclusive run (3301..3310) spanning both mask
    boxes, so a single colour and a distribution can never both be selected,
    while Heads and Bodies each open their own run.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest

try:  # Pillow is optional; source-only checkouts must still run the suite
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RC = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.rc"
SRC = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
HEADER = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_head_buckets.h"

# The shared right-column geometry, taken from the four games that already
# agree on it. Same captions, same boxes, same coordinates.
SHARED_GROUPS = (
    ('"Village-wide Heads"', 382, 2, 232, 104),
    ('"Village-wide Bodies"', 382, 110, 232, 40),
    ('"Village-wide Single Mask Color"', 382, 152, 232, 62),
)


def dialog() -> str:
    text = RC.read_text(encoding="utf-8", errors="surrogateescape")
    start = text.index('CAPTION "Change Appearance for All"')
    return text[start : text.index("\nEND", start)]


class LayoutMatchesTheOtherGamesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dlg = dialog()
        cls.rc = RC.read_text(encoding="utf-8", errors="surrogateescape")

    def test_the_dialog_is_the_shared_two_column_size(self) -> None:
        self.assertRegex(self.rc, r"214 DIALOGEX 0, 0, 620, 340")

    def test_it_centres_like_the_others(self) -> None:
        """Every other game's copy carries DS_CENTER; VV3's did not."""
        head = self.rc[self.rc.index("214 DIALOGEX"):]
        self.assertIn("DS_CENTER", head[: head.index("CAPTION")])

    def test_all_three_village_wide_groups_exist_at_the_shared_geometry(self) -> None:
        for caption, x, y, w, h in SHARED_GROUPS:
            with self.subTest(group=caption):
                self.assertRegex(
                    self.dlg,
                    r"GROUPBOX\s+%s, -1, %d, %d, %d, %d" % (re.escape(caption), x, y, w, h),
                    caption + " is missing or not at the shared position",
                )

    def test_the_mask_distribution_box_runs_full_width_along_the_bottom(self) -> None:
        self.assertRegex(
            self.dlg,
            r'GROUPBOX\s+"Mask Distribution \(all villagers\)", -1, 6, 218, 608, 80',
        )

    def test_the_head_override_offers_off_random_and_five_hair_colours(self) -> None:
        for rid in range(3400, 3407):
            with self.subTest(id=rid):
                self.assertRegex(self.dlg, r"AUTORADIOBUTTON\s+\"[^\"]+\", %d," % rid)

    def test_the_body_override_offers_off_and_random(self) -> None:
        for rid in (3410, 3411):
            with self.subTest(id=rid):
                self.assertRegex(self.dlg, r"AUTORADIOBUTTON\s+\"[^\"]+\", %d," % rid)


class ControlIdsDoNotCollideTests(unittest.TestCase):
    def test_the_override_ids_avoid_the_female_panel(self) -> None:
        """3220..3229 is VV3's female panel, which is why the 3400 block exists."""
        src = SRC.read_text(encoding="utf-8", errors="surrogateescape")
        self.assertIn("#define IDC_CAF_F_BODY   3221", src)
        self.assertIn("#define IDC_CAF_HEAD_FIRST 3400", src)
        self.assertIn("#define IDC_CAF_BODY_FIRST 3410", src)
        for rid in range(3220, 3230):
            with self.subTest(id=rid):
                self.assertNotRegex(
                    dialog(),
                    r"AUTORADIOBUTTON\s+\"[^\"]+\", %d," % rid,
                    "an override radio landed on a female-panel id",
                )

    def test_the_mask_radios_are_still_one_exclusive_run(self) -> None:
        """A single colour and a distribution must never both be selectable."""
        dlg = dialog()
        run = [rid for rid in range(3301, 3311)
               if re.search(r"AUTORADIOBUTTON\s+\"[^\"]+\", %d," % rid, dlg)]
        self.assertEqual(run, list(range(3301, 3311)))
        first = dlg.index(", 3301,")
        rest = dlg[dlg.index(", 3302,"):dlg.index(", 3310,")]
        self.assertIn("WS_GROUP", dlg[first:first + 120])
        self.assertNotIn("WS_GROUP", rest,
                         "a WS_GROUP inside the mask run would split it in two")


class MaskColumnKeepsItsHeaderTests(unittest.TestCase):
    """The colour name must not eat the column label.

    The code has always called SetDlgItemTextA on IDC_CAF_M_MASK_T (3210) and
    IDC_CAF_F_MASK_T (3230), but no control carried those ids, so the mask
    colour name was silently never shown. Giving the ids to the "Mask" HEADER
    made it live and immediately replaced the word "Mask" with "No change",
    leaving the third column unlabelled while Body and Head kept theirs. The
    ids therefore belong on their own statics under the cells.
    """

    def test_the_header_still_reads_mask(self) -> None:
        dlg = dialog()
        self.assertRegex(dlg, r'CTEXT\s+"Mask", -1, 272, 12, 50, 9')
        self.assertRegex(dlg, r'CTEXT\s+"Mask", -1, 272, 120, 50, 9')

    def test_the_colour_name_has_its_own_control(self) -> None:
        dlg = dialog()
        for rid in (3210, 3230):
            with self.subTest(id=rid):
                self.assertRegex(dlg, r'CTEXT\s+"", %d,' % rid)

    def test_those_controls_sit_inside_their_panels(self) -> None:
        """The male panel is 6,2,368,104 and the female 6,110,368,104."""
        dlg = dialog()
        for rid, top, bottom in ((3210, 2, 106), (3230, 110, 214)):
            with self.subTest(id=rid):
                m = re.search(r'CTEXT\s+"", %d, \d+, (\d+), \d+, (\d+)' % rid, dlg)
                self.assertIsNotNone(m)
                y, h = int(m.group(1)), int(m.group(2))
                self.assertGreater(y, top)
                self.assertLessEqual(y + h, bottom)


class BehaviourIsWiredTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = SRC.read_text(encoding="utf-8", errors="surrogateescape")

    def test_an_override_greys_the_selectors_it_supersedes(self) -> None:
        self.assertIn("caf_set_head_body_enable", self.src)
        fn = self.src[self.src.index("static void caf_set_head_body_enable"):]
        fn = fn[: fn.index("\n}")]
        for ctl in ("IDC_CAF_M_HEAD_P", "IDC_CAF_F_HEAD_P",
                    "IDC_CAF_M_BODY_P", "IDC_CAF_F_BODY_P"):
            with self.subTest(control=ctl):
                self.assertIn(ctl, fn)

    def test_the_result_is_planned_once_and_reused(self) -> None:
        """Preflight and apply must agree, or a random draw is charged twice over."""
        fn = self.src[self.src.index("static int vv3_apply_for_all"):]
        fn = fn[: fn.index("\n#define VW_RUNNING")]
        self.assertIn("plan_head[i]", fn)
        self.assertIn("plan_body[i]", fn)
        self.assertNotIn("int h = sex[i] ? head_f : head_m;", fn,
                         "a pass still re-derives the value instead of using the plan")

    def test_an_override_counts_as_a_change_and_warns_about_genetics(self) -> None:
        self.assertIn("|| caf_head_mode != 0 || caf_body_mode != 0", self.src)
        self.assertIn("caf_f_head >= 0 || caf_head_mode != 0", self.src)

    def test_the_bucket_pick_maps_gender_correctly(self) -> None:
        """vv3_head_pick takes 1=male; sex[] here is 1=female."""
        self.assertIn("vv3_head_pick(!sex[i], head_mode - 2, &head_rng)", self.src)


class DefectsFoundInReviewTests(unittest.TestCase):
    """Two bugs that review caught and the first version of this file did not.

    The original tests asserted the handlers and the groups EXISTED. Both
    defects were about position, which existence checks cannot see.
    """

    def test_the_override_handlers_are_not_nested_in_the_mask_branch(self) -> None:
        """3400..3411 can never satisfy a 3301..3310 test.

        Nested there, both modes stayed zero: the radio looked selected through
        the control's own behaviour while OK saw no override at all -- the
        whole feature was inert.
        """
        src = SRC.read_text(encoding="utf-8", errors="surrogateescape")
        body = src[src.index("} else if (msg == WM_COMMAND) {"):]
        body = body[: body.index("        switch (id) {")]
        head_at = body.index("id >= IDC_CAF_HEAD_FIRST")
        body_at = body.index("id >= IDC_CAF_BODY_FIRST")
        mask_at = body.index("id >= IDC_CAF_MODE_FIRST")
        self.assertLess(head_at, mask_at,
                        "the Head handler must run before the mask branch")
        self.assertLess(body_at, mask_at,
                        "the Body handler must run before the mask branch")

    def test_no_left_panel_crosses_the_full_width_bottom_group(self) -> None:
        """The bottom group starts at y=218; a 110-tall female panel ends at 226."""
        dlg = dialog()
        for caption in ('"Male Villagers"', '"Female Villagers"'):
            with self.subTest(panel=caption):
                m = re.search(
                    r"GROUPBOX\s+%s, -1, \d+, (\d+), \d+, (\d+)" % re.escape(caption),
                    dlg,
                )
                self.assertIsNotNone(m, caption + " is missing")
                top, height = int(m.group(1)), int(m.group(2))
                self.assertLessEqual(
                    top + height, 218,
                    caption + " overlaps the Mask Distribution group",
                )

    def test_every_panel_child_stays_inside_its_panel(self) -> None:
        """Shrinking the panels to 104 must not leave a control hanging out."""
        dlg = dialog()
        panels = {}
        for caption in ('"Male Villagers"', '"Female Villagers"'):
            m = re.search(
                r"GROUPBOX\s+%s, -1, \d+, (\d+), \d+, (\d+)" % re.escape(caption), dlg)
            panels[caption] = (int(m.group(1)), int(m.group(1)) + int(m.group(2)))
        # the mask colour statics are the two that sit lowest in each panel
        for rid, caption in ((3210, '"Male Villagers"'), (3230, '"Female Villagers"')):
            with self.subTest(id=rid):
                m = re.search(r'CTEXT\s+"", %d, \d+, (\d+), \d+, (\d+)' % rid, dlg)
                self.assertIsNotNone(m)
                bottom = int(m.group(1)) + int(m.group(2))
                self.assertLessEqual(bottom, panels[caption][1],
                                     "the mask colour text hangs below its panel")


class BucketsAreGeneratedTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_PIL, "requires Pillow")
    def test_the_committed_header_matches_the_head_sheets(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_vv3_head_hair_buckets.py"), "--check"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_head_is_classified_exactly_once(self) -> None:
        text = HEADER.read_text(encoding="utf-8")
        for name in ("vv3_head_bucket_m_count", "vv3_head_bucket_f_count"):
            with self.subTest(table=name):
                row = re.search(name + r"\[VV3_HAIR_COLOURS\] = \{ ([^}]+) \}", text)
                self.assertIsNotNone(row)
                counts = [int(v) for v in row.group(1).split(",")]
                self.assertEqual(len(counts), 5)
                self.assertEqual(sum(counts), 30,
                                 "every one of the 30 heads must land in exactly one bucket")


if __name__ == "__main__":
    unittest.main()
