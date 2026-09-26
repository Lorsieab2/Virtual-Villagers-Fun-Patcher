"""Every appearance chooser must offer all the options that game's ART holds.

The authoritative counts, per sex:

    game   heads   bodies
    VV1      20      20
    VV2      30      30
    VV3      30      30
    VV4      30      30
    VV5      30      30

CREATION RNG IS NOT THE CRITERION, and an earlier version of this file used it,
which is exactly how options stayed hidden. The engine only ever hands out a
SUBSET of the art it ships:

  * VV4 and VV5 roll `rand(29)` into the body field, so body 29 is never
    assigned at creation -- but the art holds thirty bodies and the chooser has
    to reach all of them.
  * VV1 rolls 19 for males and 20 for females, so male index 19 is never
    assigned -- but it exists.

Sizing a chooser to the RNG range therefore *looks* well-sourced and silently
drops the last option. Size it to the art.

The art is unambiguous. Head atlases are 65px rows: VV1's are 280x1300 (20 rows)
and the rest are 1950px tall (30). Body sheets are 640x650 grids of 64x65, i.e.
100 cells each, at 20 animation frames per body: VV1 ships four sheets per sex
(400 cells -> 20 bodies) and the rest ship six (600 -> 30).
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Optional: the read-only vanilla installs, used to re-derive the table below.
VANILLA = Path(
    os.environ.get(
        "VVFP_VANILLA_GAMES",
        # A neutral default: this file ships in the source archive, so the
        # fallback must not name anyone's machine or say which games they own.
        "vanilla-ldw-games",
    )
)
INSTALL_NAME = {
    "vv1": "Virtual Villagers - A New Home",
    "vv2": "Virtual Villagers - The Lost Children",
    "vv3": "Virtual Villagers - The Secret City",
    "vv4": "Virtual Villagers - The Tree of Life",
    "vv5": "Virtual Villagers - New Believers",
}

HEAD_ROW_PX = 65

EXPECTED = {
    "vv1": {"heads": 20, "bodies": 20},
    "vv2": {"heads": 30, "bodies": 30},
    "vv3": {"heads": 30, "bodies": 30},
    "vv4": {"heads": 30, "bodies": 30},
    "vv5": {"heads": 30, "bodies": 30},
}

# Where each game declares its counts. VV1 is per sex; VV2 uses one macro for
# heads and bodies alike.
DECLARED = {
    "vv1": {
        "source": "native/vv1_origins_icons/vv1_origins_icons.c",
        "heads": ("VV_HEAD_COUNT_M", "VV_HEAD_COUNT_F"),
        "bodies": ("VV_BODY_COUNT_M", "VV_BODY_COUNT_F"),
    },
    "vv2": {
        "source": "native/vv2_origins_icons/vv2_origins_icons.c",
        "heads": ("VV2_APPEARANCE_COUNT",),
        "bodies": ("VV2_APPEARANCE_COUNT",),
    },
    "vv3": {
        "source": "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
        "heads": ("VV3_HEAD_COUNT",),
        "bodies": ("VV3_BODY_COUNT",),
    },
    "vv4": {
        "source": "native/vv4_origins_icons/vv4_origins_icons.c",
        "heads": ("VV_HEAD_COUNT",),
        "bodies": ("VV_BODY_COUNT",),
    },
    "vv5": {
        "source": "native/vv5_task9_origins/vv5_task9_origins.c",
        "heads": ("APPEARANCE_HEAD_COUNT",),
        "bodies": ("APPEARANCE_BODY_COUNT",),
    },
}


def _macro(source: str, name: str) -> int | None:
    text = (ROOT / source).read_text(encoding="utf-8")
    match = re.search(rf"^#define {re.escape(name)} (\d+)$", text, re.M)
    return int(match.group(1)) if match else None


class AppearanceOptionCountTests(unittest.TestCase):
    """Reads committed sources, so it runs in a clean checkout."""

    def test_every_chooser_offers_every_option_the_art_holds(self) -> None:
        for game, wanted in EXPECTED.items():
            spec = DECLARED[game]
            for kind in ("heads", "bodies"):
                for macro in spec[kind]:
                    with self.subTest(game=game, kind=kind, macro=macro):
                        value = _macro(spec["source"], macro)
                        self.assertIsNotNone(
                            value, f"{macro} not found in {spec['source']}"
                        )
                        self.assertEqual(
                            value, wanted[kind],
                            f"{game} offers {value} {kind}; the art holds "
                            f"{wanted[kind]}, so a player cannot reach every "
                            f"appearance the game ships",
                        )

    def test_embedded_preview_strips_have_a_cell_for_every_choice(self) -> None:
        """The owner-drawn preview must not run off the end of its bitmap."""
        strips = {
            "vv1": ("native/vv1_origins_icons/appearance", (
                ("head_m.bmp", 20, "vertical"), ("head_f.bmp", 20, "vertical"),
                ("body_m.bmp", 20, "vertical"), ("body_f.bmp", 20, "vertical"),
                ("mask.bmp", 6, "vertical"),
            )),
            "vv2": ("native/vv2_origins_icons/appearance", (
                *((name, 30, "horizontal") for name in (
                    "head_m_young.bmp", "head_m_old.bmp", "head_f_young.bmp",
                    "head_f_old.bmp", "body_m.bmp", "body_f.bmp")),
                ("mask_preview.bmp", 6, "horizontal"),
            )),
            "vv3": ("native/vv3_full_mastery_candidate/appearance", (
                *((name, 30, "horizontal") for name in (
                    "head_m_young.bmp", "head_m_old.bmp", "head_f_young.bmp",
                    "head_f_old.bmp", "body_m.bmp", "body_f.bmp")),
                ("mask_strip.bmp", 6, "horizontal"),
            )),
            "vv4": ("assets/vv4_masks", (("vvfp_mask_preview.png", 6, "horizontal"),)),
            "vv5": ("native/vv5_task9_origins/appearance", (
                *((name, 30, "horizontal") for name in (
                    "head_m_young.bmp", "head_m_old.bmp", "head_f_young.bmp",
                    "head_f_old.bmp", "body_m.bmp", "body_f.bmp")),
                ("mask_preview.bmp", 6, "horizontal"),
            )),
        }
        from PIL import Image, ImageChops

        for game, (directory, files) in strips.items():
            for filename, expected_cells, orientation in files:
                path = ROOT / directory / filename
                with self.subTest(game=game, file=filename):
                    with Image.open(path) as image:
                        width, height = image.size
                        cell_w, cell_h = (40, 65)
                        cells = height // cell_h if orientation == "vertical" else width // cell_w
                        self.assertEqual(
                            cells, expected_cells,
                            f"{filename} has {cells} cells; the selector offers {expected_cells}",
                        )
                        if "mask" in filename:
                            indices = range(1, expected_cells)  # index 0 is the intentional no-mask cell
                        else:
                            indices = range(expected_cells)
                        pixels = image.convert("RGB")
                        for index in indices:
                            if orientation == "vertical":
                                cell = pixels.crop((0, index * cell_h, cell_w, (index + 1) * cell_h))
                            else:
                                cell = pixels.crop((index * cell_w, 0, (index + 1) * cell_w, cell_h))
                            self.assertNotEqual(
                                ImageChops.difference(
                                    cell, Image.new("RGB", cell.size, (236, 236, 236))
                                ).getbbox(), None,
                                f"{filename} cell {index} is blank",
                            )

    def test_vv4_live_atlas_picker_uses_all_rows_and_the_requested_body_frame(self) -> None:
        source = (ROOT / "native/vv4_origins_icons/vv4_origins_icons.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("#define VV_HEAD_COUNT 30", source)
        self.assertIn("#define VV_BODY_COUNT 30", source)
        self.assertIn("#define VV_BODY_FRAME_COL 8", source)
        draw = source.split("static void appearance_draw_cell(", 1)[1].split("\n}", 1)[0]
        self.assertIn("row = value;", draw)
        self.assertIn("page = value / VV_BODY_ROWS_PER_PAGE;", draw)
        self.assertIn("row = value % VV_BODY_ROWS_PER_PAGE;", draw)

    def test_all_games_use_body_pose_frame_index_8(self) -> None:
        sources = {
            "vv1": ("scripts/build_vv1_appearance_bitmaps.py", "BODY_FRAME = 8"),
            "vv2": ("scripts/build_vv2_appearance_sheets.py", "BODY_FRAME = 8"),
            "vv3": ("scripts/build_vv3_appearance_bmps.py", "BODY_FRAME = 8"),
            "vv4": ("native/vv4_origins_icons/vv4_origins_icons.c", "#define VV_BODY_FRAME_COL 8"),
            "vv5": ("scripts/build_vv5_appearance_sheets.py", "BODY_FRAME = 8"),
        }
        for game, (path, expected) in sources.items():
            with self.subTest(game=game):
                self.assertIn(expected, (ROOT / path).read_text(encoding="utf-8"))

    def test_both_sexes_get_the_same_number_of_options(self) -> None:
        """VV1 is the only per-sex declaration, and both sexes are 20."""
        spec = DECLARED["vv1"]
        for kind in ("heads", "bodies"):
            male, female = (_macro(spec["source"], m) for m in spec[kind])
            with self.subTest(kind=kind):
                self.assertEqual(
                    (male, female), (20, 20),
                    "VV1's male count was 19 because creation rolls rand(19) "
                    "for males; the art holds twenty and both sexes must be "
                    "able to reach all of them",
                )

    @unittest.skipUnless(VANILLA.is_dir(), "vanilla game installs are not present")
    def test_the_expected_table_is_re_derived_from_the_art(self) -> None:
        """Count populated value rows, grouping body pages by age correctly."""
        from PIL import Image

        for game, wanted in EXPECTED.items():
            images = VANILLA / INSTALL_NAME[game] / "Images"
            self.assertTrue(images.is_dir(), f"missing vanilla Images folder for {game}")
            with self.subTest(game=game):
                for sex in ("male", "female"):
                    heads = sorted(images.glob(f"{sex}_heads*.png"))
                    self.assertEqual(len(heads), 1 if game == "vv1" else 2)
                    for path in heads:
                        with Image.open(path) as image:
                            rows = image.height // HEAD_ROW_PX
                            alpha = image.convert("RGBA").getchannel("A")
                            populated = sum(
                                alpha.crop((0, row * HEAD_ROW_PX, image.width,
                                            (row + 1) * HEAD_ROW_PX)).getbbox() is not None
                                for row in range(rows)
                            )
                        self.assertEqual((rows, populated), (wanted["heads"], wanted["heads"]),
                                         f"{path.name}: not every head row is populated")

                    body_files = sorted(images.glob(f"{sex}_bodies*.png"))
                    self.assertTrue(body_files, f"no body sheets for {game} {sex}")
                    groups: dict[str, list[Path]] = {}
                    for path in body_files:
                        suffix = path.stem.removeprefix(f"{sex}_bodies")
                        # VV1's two suffix digits are column-block then row-block;
                        # the first digit duplicates the same value rows.
                        key = suffix[1] if game == "vv1" else suffix[0]
                        groups.setdefault(key, []).append(path)
                    group_row_counts = []
                    for group, pages in groups.items():
                        if game == "vv1":
                            # One representative column block per row page.
                            pages = [next(p for p in pages if p.stem.endswith("0" + group))]
                        rows_in_group = 0
                        for path in pages:
                            with Image.open(path) as image:
                                rows = image.height // HEAD_ROW_PX
                                alpha = image.convert("RGBA").getchannel("A")
                                populated = sum(
                                    alpha.crop((0, row * HEAD_ROW_PX, image.width,
                                                (row + 1) * HEAD_ROW_PX)).getbbox() is not None
                                    for row in range(rows)
                                )
                            self.assertEqual(populated, rows, f"{path.name}: blank body row")
                            rows_in_group += rows
                        group_row_counts.append(rows_in_group)
                        expected_group_rows = 10 if game == "vv1" else wanted["bodies"]
                        self.assertEqual(
                            rows_in_group, expected_group_rows,
                            f"{game} {sex} age/page group {group} has {rows_in_group} body rows",
                        )
                    if game == "vv1":
                        self.assertEqual(sum(group_row_counts), wanted["bodies"])

    def test_the_whole_village_cyclers_use_the_same_counts(self) -> None:
        """Change Appearance for All must offer what Change Appearance offers.

        Both halves of this were real: VV1's per-sex cyclers hardcoded 19 and 20
        as literals, so raising the macros left the male controls wrapping after
        18; and VV5's Tech-screen implementation kept its OWN body count, so
        body 29 was reachable only from the individual chooser.
        """
        vv1 = (ROOT / DECLARED["vv1"]["source"]).read_text(encoding="utf-8")
        cyclers = re.findall(
            r"forall_cycle\(forall_state\.(male|female)_(head|body), [-+]1, ([^)]+)\)",
            vv1,
        )
        self.assertGreaterEqual(len(cyclers), 8, "expected both axes for both sexes")
        for sex, kind, count in cyclers:
            with self.subTest(sex=sex, kind=kind):
                self.assertFalse(
                    count.strip().isdigit(),
                    f"VV1's {sex} {kind} cycler uses the literal {count.strip()}; "
                    f"it must read the macro or the two choosers drift apart",
                )

        vv5 = (ROOT / DECLARED["vv5"]["source"]).read_text(encoding="utf-8")
        for shared, individual in (("VV5_HEAD_COUNT", "APPEARANCE_HEAD_COUNT"),
                                   ("VV5_BODY_COUNT", "APPEARANCE_BODY_COUNT")):
            with self.subTest(macro=shared):
                self.assertIn(
                    f"#define {shared} {individual}", vv5,
                    f"VV5's whole-village {shared} must track {individual} "
                    f"rather than carrying its own number",
                )

    def test_creation_rng_is_not_used_as_the_criterion(self) -> None:
        """The specific regression this file exists to prevent.

        Each of these is a value some game's creation RNG rolls. If a chooser is
        ever resized to one, the last option disappears again -- silently,
        because the number looks well-sourced.
        """
        rng_subsets = {"vv1": 19, "vv4": 29, "vv5": 29}
        for game, subset in rng_subsets.items():
            spec = DECLARED[game]
            for kind in ("heads", "bodies"):
                for macro in spec[kind]:
                    value = _macro(spec["source"], macro)
                    with self.subTest(game=game, macro=macro):
                        self.assertNotEqual(
                            value, subset,
                            f"{game}'s {macro} is {subset}, the creation RNG "
                            f"range -- not the number of options in the art",
                        )


if __name__ == "__main__":
    unittest.main()
