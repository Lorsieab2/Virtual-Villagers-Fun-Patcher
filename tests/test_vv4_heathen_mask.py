"""Static regression tests for the VV4 Heathen-mask overlay render side.

A render hook can only be *proven* in-game, but the pieces that feed it are
statically checkable and easy to break silently:

* ``build_vv4_mask_atlas`` must append the 5 masks as head-atlas rows 30..34
  while leaving the original 30 head rows byte-for-byte intact (the user's
  "don't crop / don't alter the head sprites" requirement).
* ``build_vv4_mask_stage1_probe``'s render-hook cave must assemble for both the
  shipping (+0x1BC4-gated) and the proof (forced-row) modes, fit its cave
  budget, and keep its documented hook constants.
* The companion DLL chooser and the render cave must agree on the ONE contract
  that ties them together: the unused per-villager byte +0x1BC4, and the
  "mask value N draws head-atlas row 29+N" mapping. If those drift apart the
  picker writes a byte the renderer reads as a different row.

None of this needs the game executable.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ATLAS_SCRIPT = ROOT / "scripts" / "build_vv4_mask_atlas.py"
PROBE_SCRIPT = ROOT / "scripts" / "build_vv4_mask_stage1_probe.py"
DLL_SOURCE = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


atlas = _load("vvfp_vv4_mask_atlas", ATLAS_SCRIPT)
probe = _load("vvfp_vv4_mask_probe", PROBE_SCRIPT)


def _fake_head_atlas() -> Image.Image:
    """A stock-geometry head atlas (320x1950, 8 frames x 30 rows of 40x65),
    with a skin-coloured blob in each sampled face row so the real face-centroid
    path (not just the fallback) runs."""
    w, h = atlas.CELL_W * atlas.FRAMES, atlas.CELL_H * atlas.HEAD_ROWS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    skin = (210, 170, 120, 255)  # passes _is_skin
    for f in range(atlas.FRAMES):
        for row in atlas.FACE_SAMPLE_ROWS:
            cx = f * atlas.CELL_W + atlas.CELL_W // 2
            cy = row * atlas.CELL_H + atlas.CELL_H // 3
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    px[cx + dx, cy + dy] = skin
    return img


def _fake_mask_sheet() -> Image.Image:
    """An 8x5 grid of 65x145 cells, each with an opaque blob so getbbox() is
    non-empty and the cell composites (a fully transparent cell would have no
    bbox and could not be placed)."""
    w = atlas.SRC_CELL_W * atlas.FRAMES
    h = atlas.SRC_CELL_H * atlas.MASK_ROWS
    sheet = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = sheet.load()
    for r in range(atlas.MASK_ROWS):
        for f in range(atlas.FRAMES):
            x0 = f * atlas.SRC_CELL_W + 20
            y0 = r * atlas.SRC_CELL_H + 40
            for dy in range(45):
                for dx in range(26):
                    px[x0 + dx, y0 + dy] = (30 + r * 40, 60, 200, 255)
    return sheet


class AtlasBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = _fake_head_atlas()
        # _native_mask_frames takes a path; slice the in-memory sheet the same way.
        sheet = _fake_mask_sheet()
        frames = []
        for r in range(atlas.MASK_ROWS):
            row = []
            for f in range(atlas.FRAMES):
                row.append(sheet.crop((
                    f * atlas.SRC_CELL_W, r * atlas.SRC_CELL_H,
                    f * atlas.SRC_CELL_W + atlas.SRC_CELL_W,
                    r * atlas.SRC_CELL_H + atlas.SRC_CELL_H)))
            frames.append(row)
        cls.frames = frames
        cls.out = atlas.build_atlas(cls.src, cls.frames)

    def test_output_has_exactly_five_appended_rows(self) -> None:
        self.assertEqual(
            self.out.size,
            (atlas.CELL_W * atlas.FRAMES,
             atlas.CELL_H * (atlas.HEAD_ROWS + atlas.MASK_ROWS)),
        )
        self.assertEqual(atlas.HEAD_ROWS, 30)
        self.assertEqual(atlas.MASK_ROWS, 5)

    def test_original_head_rows_are_byte_identical(self) -> None:
        """"Don't crop / don't alter the head sprites": the first 30 rows of the
        output must equal the source exactly."""
        w = self.src.size[0]
        head_h = atlas.CELL_H * atlas.HEAD_ROWS
        self.assertEqual(
            self.out.crop((0, 0, w, head_h)).tobytes(),
            self.src.tobytes(),
        )

    def test_masks_actually_land_in_the_appended_rows(self) -> None:
        w = self.src.size[0]
        head_h = atlas.CELL_H * atlas.HEAD_ROWS
        appended = self.out.crop((0, head_h, w, self.out.size[1]))
        # At least one opaque mask pixel per appended row band.
        px = appended.load()
        for r in range(atlas.MASK_ROWS):
            band_opaque = any(
                px[x, r * atlas.CELL_H + y][3] > 0
                for y in range(atlas.CELL_H)
                for x in range(w)
            )
            self.assertTrue(band_opaque, f"mask row {r} is empty")

    def test_head_atlas_filenames_cover_both_sexes_and_ages(self) -> None:
        self.assertEqual(
            set(atlas.HEAD_ATLASES),
            {"male_heads00.png", "male_heads10.png",
             "female_heads00.png", "female_heads10.png"},
        )


class ProbeCaveTests(unittest.TestCase):
    CAVE_BUDGET = 0x48A000 - 0x489019

    def test_hook_constants_are_the_documented_ones(self) -> None:
        # Both render twins (walking + selection-panel portraits).
        self.assertEqual(probe.CALL_SITES, (0x45F702, 0x45F9CA))
        self.assertEqual(probe.DRAW, 0x409A70)
        self.assertEqual(probe.CAVE, 0x489019)
        # Head-atlas row-count fields bumped 30 -> 35 (male + female sheets).
        self.assertEqual(probe.ROW_FIELDS, {0xC3C24: (30, 35), 0xC3B94: (30, 35)})

    def _assemble(self, force_row):
        prologue = probe._cave_asm(0, force_row).split("post_head:")[0]
        post_head = probe.CAVE + len(probe._assemble(prologue, probe.CAVE))
        return probe._assemble(probe._cave_asm(post_head, force_row), probe.CAVE)

    def test_gated_cave_assembles_and_fits(self) -> None:
        cave = self._assemble(None)
        self.assertGreater(len(cave), 0)
        self.assertLessEqual(len(cave), self.CAVE_BUDGET)

    def test_forced_proof_cave_assembles_and_fits(self) -> None:
        cave = self._assemble(probe.MASK_ROW)  # 30 = Blue
        self.assertGreater(len(cave), 0)
        self.assertLessEqual(len(cave), self.CAVE_BUDGET)

    def test_only_the_gated_mode_reads_the_mask_byte(self) -> None:
        gated = probe._cave_asm(0, None)
        forced = probe._cave_asm(0, probe.MASK_ROW)
        self.assertIn("0x1BC4", gated)
        self.assertIn("add eax, 29", gated)   # mask N -> atlas row 29+N
        self.assertNotIn("0x1BC4", forced)

    def test_scratch_slots_clear_the_barrel_region(self) -> None:
        # The probe's scratch slots must sit past the barrel payload
        # (0x728B00..0x728C04) and before Collections (0x728D00).
        slots = (probe.S_ECX, probe.S_A0, probe.S_A1, probe.S_A2,
                 probe.S_A4, probe.S_A5, probe.S_RET)
        for s in slots:
            self.assertGreaterEqual(s, 0x728C40)
            self.assertLess(s, 0x728D00)


class ChooserRendererContractTests(unittest.TestCase):
    """The DLL picker writes +0x1BC4; the cave reads +0x1BC4. They must agree on
    the offset and the value->row mapping, or the picker and the world disagree."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.c = DLL_SOURCE.read_text(encoding="utf-8", errors="replace")

    def test_dll_uses_the_same_mask_byte_as_the_cave(self) -> None:
        self.assertIn("#define VV_MASK_OFFSET 0x1BC4", self.c)
        # The probe cave gate reads the identical byte.
        self.assertIn("0x1BC4", probe._cave_asm(0, None))

    def test_dll_uses_the_same_29_plus_mask_row_mapping(self) -> None:
        # Preview overlay draws atlas row (29 + mask), matching the cave's
        # "add eax, 29" after loading the 1..5 mask byte.
        self.assertIn("29 + mask", self.c)

    def test_mask_table_is_none_plus_five(self) -> None:
        self.assertIn("#define VV_MASK_COUNT 6", self.c)
        table = self.c.split("g_mask_names[VV_MASK_COUNT] = {", 1)[1].split("};", 1)[0]
        # Six comma-separated string entries: (None) + 5 masks.
        self.assertEqual(table.count('"') // 2, 6)
        for label in ("(None)", "Blue Mask", "Orange Mask",
                      "Red Mask", "Purple Mask", "Tribal Chief Mask"):
            self.assertIn(label, table)


if __name__ == "__main__":
    unittest.main()
