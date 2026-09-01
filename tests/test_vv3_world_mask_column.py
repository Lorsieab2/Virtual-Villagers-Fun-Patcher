"""VV3's village-view mask must pick its atlas column explicitly.

`docs/head-mask-rendering.md` Part 6 rule 3: select the mask column yourself,
never reuse the head's frame index, because the head atlas and the mask atlas
have different column layouts.

VV1 is allowed to replay `args[4]` straight through -- its mask atlas was built
to share its head atlas' column layout, which the source says explicitly. VV3's
was not. `assets/vv3_heathen_masks/heathen_masks.png` is 520x725: eight facing
columns by five colour rows of 65x145, the same shape as VV5's native village
atlas.

VV3's world draw already extracted `facing = args[4] & 7` -- the mask proves
`args[4]` is a composite whose facing is only the low three bits -- but then
passed the raw composite through as the column, so it indexed past column 7 and
drew the wrong cell. This pins the corrected behaviour.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
)
ATLAS = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png"

ATLAS_COLS = 8      # facings
ATLAS_ROWS = 5      # Blue / Orange / Red / Purple / Chief
CELL_W, CELL_H = 65, 145


def _world_draw_body(text: str) -> str:
    # Match the DEFINITION, not the forward declaration: require the closing
    # paren to be followed by `{` rather than `;`.
    match = re.search(
        r"void\s+__stdcall\s+VV3WorldMaskDrawAt\s*\([^)]*\)\s*\{", text
    )
    if match is None:
        raise AssertionError("VV3WorldMaskDrawAt definition not found")
    brace = match.end() - 1
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace:index + 1]
    raise AssertionError("unbalanced braces in VV3WorldMaskDrawAt")


class VV3WorldMaskColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.body = _world_draw_body(cls.source)

    def test_the_column_is_assigned_from_facing(self) -> None:
        self.assertIn(
            "mask_args[4] = facing;", self.body,
            "the village-view mask column is not set from the villager's "
            "facing; replaying the head's composite args[4] indexes past the "
            "atlas' eight facing columns and draws the wrong cell",
        )

    def test_facing_is_masked_to_the_atlas_column_range(self) -> None:
        self.assertIn("facing = mask_args[4] & 7;", self.body)
        # The mask itself is the evidence that args[4] is a composite.
        self.assertLess(
            self.body.index("facing = mask_args[4] & 7;"),
            self.body.index("mask_args[4] = facing;"),
            "facing must be extracted before it overwrites the column",
        )

    def test_the_colour_row_is_the_mask_index_not_head_derived(self) -> None:
        self.assertIn("mask_args[3] = mask - 1;", self.body)

    def test_the_rest_of_the_head_tuple_is_replayed_untouched(self) -> None:
        """Only the atlas, row and column may differ from the head's own draw.

        Position, scale and the renderer wrapper have to be inherited, or the
        mask stops tracking the villager.
        """
        self.assertIn("for (i = 0; i < 6; ++i) mask_args[i] = args[i];", self.body)
        assigned = set(re.findall(r"mask_args\[(\d)\]\s*=", self.body))
        self.assertEqual(
            assigned, {"0", "3", "4"},
            f"the world mask overwrites head-tuple slots {sorted(assigned)}; "
            f"only the atlas (0), colour row (3) and facing column (4) may "
            f"differ from the replayed head draw",
        )

    @unittest.skipUnless(ATLAS.is_file(), "mask atlas not present")
    def test_the_atlas_really_is_eight_facings_by_five_colours(self) -> None:
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover - Pillow is a dev dependency
            self.skipTest("Pillow unavailable")
        width, height = Image.open(ATLAS).size
        self.assertEqual(
            (width, height), (ATLAS_COLS * CELL_W, ATLAS_ROWS * CELL_H),
            "the atlas geometry changed; the facing-column mapping above "
            "assumes eight 65x145 columns across five colour rows",
        )


if __name__ == "__main__":
    unittest.main()
