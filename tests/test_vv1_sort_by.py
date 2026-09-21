"""Sort by Age/Skill/Health in Details Screen (A New Home): the companion, its
manifest and art, the two arrow hooks in the Origins patch, and the rule.

The rule was measured live in The Secret City and is exercised at runtime by
native/vv1_sort_by/vv1_sort_by_harness.c (32-bit, loads the built DLL).
This file pins what Python can check: the shipped DLL and images are the
ones the manifest names, the DLL exports what the Origins companion calls,
the offsets the companion reads are the measured VV1 ones, the executable
really has the two six-byte stores the hooks splice, the generated stubs
are what the review note describes, and the feature is registered, bundled
and documented.
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
DLL = ROOT / "assets" / "sort_by" / "VVFP VV1 Sort By.dll"
MANIFEST = ROOT / "data" / "vv1_sort_by_feature.json"
ORIGINS_MANIFEST = ROOT / "data" / "vv1_origins_feature.json"
SORT_C = ROOT / "native" / "vv1_sort_by" / "vv1_sort_by.c"
HARNESS_C = ROOT / "native" / "vv1_sort_by" / "vv1_sort_by_harness.c"
ORIGINS_C = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
PARENTAGE_C = ROOT / "native" / "vv1_parentage" / "vv1_parentage.c"

ART = ("vvfp_sort_band.png", "vvfp_sort_radio.png")


def _define(source: str, name: str) -> int:
    match = re.search(r"#define\s+%s\s+(0x[0-9A-Fa-f]+|-?\d+)" % re.escape(name), source)
    assert match, name
    return int(match.group(1), 0)


class ManifestAndDllTests(unittest.TestCase):
    def test_manifest_pins_the_shipped_files(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        pinned = {f["destination"]: f["sha256"].upper() for f in manifest["companion_files"]}
        self.assertEqual(pinned["VVFP VV1 Sort By.dll"], hashlib.sha256(DLL.read_bytes()).hexdigest().upper())
        for name in ART:
            self.assertEqual(pinned["Images/" + name], hashlib.sha256((ROOT / "assets" / "sort_by" / name).read_bytes()).hexdigest().upper(), name)
        self.assertEqual(manifest["patches"], [], "the row changes no executable bytes itself")
        self.assertEqual(manifest["dependencies"], ["vv1_enable_origins_exclusive_features"])
        self.assertTrue(manifest["enabled"])

    def test_art_is_png_and_the_radio_is_a_three_cell_sheet_of_16px(self):
        for name in ART:
            data = (ROOT / "assets" / "sort_by" / name).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", name)
        from PIL import Image
        radio = Image.open(ROOT / "assets" / "sort_by" / "vvfp_sort_radio.png")
        self.assertEqual(radio.height, 16, "the owner: the radio selector is 16x16")
        self.assertEqual(radio.width, radio.height * 3, "three square cells: blank, selected, selected")
        band = Image.open(ROOT / "assets" / "sort_by" / "vvfp_sort_band.png")
        self.assertEqual(band.size, (258, 40), "the strip the owner changed in the Details background")
        source = SORT_C.read_text(encoding="utf-8")
        self.assertIn('vv1_sprite(&g_radio_sprite, "vvfp_sort_radio.png", 3, 1)', source)
        self.assertIn('vv1_sprite(&g_band_sprite, "vvfp_sort_band.png", 1, 1)', source)
        self.assertEqual(_define(source, "SORT_RADIO_SIZE"), 16)
        self.assertNotIn("vv1_draw_text_scaled", source, "the words are in the art; no custom text scaling (the owner)")

    def test_the_watch_inverts_sdls_event_reduction_before_hit_testing(self):
        """SDL 2.0.3 reduces the button event, so our watch must UN-reduce it.

        Measured against the running game in fullscreen (SDL reported
        scale 1.78, viewport origin 79, at window 1707x1068 over the logical
        800x600 band): SDL_RendererEventWatch runs before this DLL's watch and
        delivers each button event as

            event = (logical - viewport) / scale

        so the band -- drawn in logical 800x600 -- is hit-tested only after the
        inverse, logical = event * scale + viewport.  Two earlier builds failed
        here: one hit-tested the event coordinates raw (they are not logical in
        fullscreen), and one DIVIDED by the scale (the wrong direction, since
        the reduction has already happened).  This pins the multiply.
        """
        source = SORT_C.read_text(encoding="utf-8")
        # the watch maps before it hits, through the helper
        self.assertIn("vv1_event_to_logical(&x, &y);", source)
        self.assertIn("hit = vv1_hit(x, y);", source)
        # the helper multiplies by the SDL scale and ADDS the viewport, never
        # divides -- a division would be the failed direction
        # The viewport comes back in LOGICAL units, so it is scaled into the
        # same space as event * scale BEFORE it is added; adding it raw mixes
        # two spaces and drags X left (#403).
        self.assertIn("(int)((float)*x * sx + (float)viewport[0] * sx)", source)
        self.assertIn("(int)((float)*y * sy + (float)viewport[1] * sy)", source)
        # the pre-#403 form, which mixed logical and window-pixel terms
        self.assertNotIn("(int)((float)*x * sx) + viewport[0]", source)
        self.assertNotIn("/ sx", source)
        self.assertNotIn("/ sy", source)
        for proc in ("SDL_GetRenderer", "SDL_RenderGetScale", "SDL_RenderGetViewport"):
            self.assertIn('GetProcAddress(sdl, "%s")' % proc, source)

        plates = ((8, 90), (95, 177), (184, 266))
        plate_centres = tuple((left + right) // 2 for left, right in plates)
        logical_y = (496 + 515) // 2

        def sdl_delivers(logical_x, logical_y, viewport, scale):
            # the viewport origin is in LOGICAL units, so it is subtracted
            # after the divide, not before it (#403)
            return (
                int(logical_x / scale - viewport[0]),
                int(logical_y / scale - viewport[1]),
            )

        def watch_recovers(event_x, event_y, viewport, scale):
            # the viewport is logical, so it is scaled before it is added back
            return (
                int(event_x * scale + viewport[0] * scale),
                int(event_y * scale + viewport[1] * scale),
            )

        for viewport, scale in (
            ((0, 0), 1.0),               # a plain window: identity
            ((79, 0), 1.78),             # the owner's measured fullscreen
            ((113, 0), 1.66),            # the owner's measured maximized (#403)
            ((240, 0), 2.4),
            ((320, 0), 3.2),
        ):
            for mode, logical_x in enumerate(plate_centres):
                ev = sdl_delivers(logical_x, logical_y, viewport, scale)
                gx, gy = watch_recovers(ev[0], ev[1], viewport, scale)
                self.assertGreaterEqual(gx, (8, 95, 184)[mode], (viewport, scale, mode))
                self.assertLess(gx, (90, 177, 266)[mode], (viewport, scale, mode))
                self.assertGreaterEqual(gy, 496, (viewport, scale))
                self.assertLess(gy, 515, (viewport, scale))

        # The earlier wrong direction (divide) missed on the Y axis in
        # fullscreen: a click on the button row came in near event y 283, and
        # 283/1.78 = 158 is nowhere near the band at y 496..515, while
        # 283*1.78 = 503 lands inside it.
        ev = sdl_delivers(plate_centres[1], logical_y, (79, 0), 1.78)
        self.assertFalse(496 <= int(ev[1] / 1.78) < 515, "dividing misses the band's row")
        self.assertTrue(496 <= int(ev[1] * 1.78) < 515, "multiplying recovers the band's row")

        # #403, measured live in the owner's maximized window (client
        # 1707x996, IsZoomed): SDL reported scale 1.66 and viewport
        # (113, 0, 800, 600).  A click aimed at the Skill plate arrived at
        # raw x -19.  The shipped form mapped it to logical 82 -- inside
        # Age, one plate to the LEFT -- so the owner had to aim right of the
        # button.  Scaling the viewport first lands it in Skill.
        raw_x, scale, viewport_x = -19, 1.66, 113
        before = int(raw_x * scale) + viewport_x
        after = int(raw_x * scale + viewport_x * scale)
        self.assertEqual(before, 82)
        self.assertTrue(8 <= before < 90, "the old form landed in Age")
        self.assertTrue(95 <= after < 177, "the fix lands the click in Skill")

        # Y is untouched by the change: the display is pillarboxed, so the
        # content fills the height and viewport[1] is 0.  That is why the
        # fullscreen verification, whose worked example was a Y coordinate,
        # never exercised the X bug.
        for scale in (1.66, 1.78):
            self.assertEqual(int(283 * scale), int(283 * scale + 0 * scale))

    def test_the_radio_positions_are_where_the_art_has_its_holders(self):
        # The holders painted into the band are the sheet's blank cell; the
        # code's SORT_RADIO_X/Y must land the selected cell exactly on them,
        # and the plates' click rects must contain them.  Measured from the
        # art, not from the code, so the two cannot drift apart silently.
        from PIL import Image
        source = SORT_C.read_text(encoding="utf-8")
        band = Image.open(ROOT / "assets" / "sort_by" / "vvfp_sort_band.png").convert("RGBA")
        radio = Image.open(ROOT / "assets" / "sort_by" / "vvfp_sort_radio.png").convert("RGBA")
        cell = radio.crop((0, 0, 16, 16))
        mask = [(x, y) for y in range(16) for x in range(16) if cell.getpixel((x, y))[3] > 128]
        self.assertGreater(len(mask), 100)
        band_x, band_y = _define(source, "SORT_BAND_X"), _define(source, "SORT_BAND_Y")
        self.assertEqual((band_x, band_y), (8, 475))
        radio_y = _define(source, "SORT_RADIO_Y")
        radio_x = [int(v) for v in re.search(r"SORT_RADIO_X\[SORT_MODES\]\s*=\s*\{([^}]*)\}", source).group(1).split(",")]
        x0 = [int(v) for v in re.search(r"SORT_PLATE_X0\[SORT_MODES\]\s*=\s*\{([^}]*)\}", source).group(1).split(",")]
        x1 = [int(v) for v in re.search(r"SORT_PLATE_X1\[SORT_MODES\]\s*=\s*\{([^}]*)\}", source).group(1).split(",")]
        y0, y1 = _define(source, "SORT_PLATE_Y0"), _define(source, "SORT_PLATE_Y1")

        def error(bx, by):
            return sum(abs(a - b) for (x, y) in mask for a, b in zip(band.getpixel((bx + x, by + y))[:3], cell.getpixel((x, y))[:3]))

        for m in range(3):
            bx, by = radio_x[m] - band_x, radio_y - band_y
            here = error(bx, by)
            self.assertLess(here / len(mask), 48, "mode %d: the sheet's blank cell is not at the code's radio spot (16 per channel)" % m)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.assertLess(here, error(bx + dx, by + dy), "mode %d: a neighbour matches better; the spot is off by one" % m)
            self.assertTrue(x0[m] <= radio_x[m] and radio_x[m] + 16 <= x1[m], "the radio inside its plate's click rect")
            self.assertTrue(y0 <= radio_y and radio_y + 16 <= y1)

    def test_dll_exports_what_origins_calls(self):
        pe = pefile.PE(str(DLL))
        names = {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        for export in ("Vv1SortByStep", "Vv1SortByDraw", "Vv1SortByMode"):
            self.assertIn(export, names)
        self.assertEqual(pe.FILE_HEADER.Machine, 0x14C)
        imports = {entry.dll.decode().lower() for entry in pe.DIRECTORY_ENTRY_IMPORT}
        self.assertTrue(imports <= {"kernel32.dll"}, imports)
        origins = ORIGINS_C.read_text(encoding="utf-8")
        self.assertIn('"VVFP VV1 Sort By.dll"', origins)
        self.assertIn('GetProcAddress(companion, "Vv1SortByStep")', origins)
        self.assertIn('GetProcAddress(companion, "Vv1SortByDraw")', origins)
        self.assertIn("__stdcall Vv1SortStep(int candidate, int direction)", origins)
        self.assertIn("vv1_sort_bridge_draw(gameobj, record, draw_wrapper, args);", origins)
        origins_dll = pefile.PE(str(ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"))
        self.assertIn("Vv1SortStep", {e.name.decode() for e in origins_dll.DIRECTORY_ENTRY_EXPORT.symbols if e.name})


class OffsetAgreementTests(unittest.TestCase):
    def test_record_fields_match_the_other_vv1_companions(self):
        sort = SORT_C.read_text(encoding="utf-8")
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        origins = ORIGINS_C.read_text(encoding="utf-8")
        self.assertEqual(_define(sort, "VV1_RECORD_STRIDE"), _define(parentage, "VV1_RECORD_STRIDE"))
        self.assertEqual(_define(sort, "VV1_OCCUPIED_OFFSET"), _define(parentage, "VV1_OCCUPIED_OFFSET"))
        self.assertEqual(_define(sort, "VV1_AGE_OFFSET"), _define(parentage, "VV1_AGE_OFFSET"))
        self.assertEqual(_define(sort, "VV1_HEALTH_OFFSET"), 0x344, "the stock arrows' own health test")
        self.assertEqual(_define(sort, "VV1_SKILLS_OFFSET"), 0x3BC)
        self.assertEqual(_define(sort, "VV1_SKILL_COUNT"), 5)
        self.assertIn("0x3BC", origins, "the Origins full-mastery walker reads the same skill table")
        harness = HARNESS_C.read_text(encoding="utf-8")
        for c_name, h_name in (("VV1_RECORD_STRIDE", "STRIDE"), ("VV1_OCCUPIED_OFFSET", "OCC"), ("VV1_HEALTH_OFFSET", "HEALTH"),
                               ("VV1_AGE_OFFSET", "AGE"), ("VV1_SKILLS_OFFSET", "SKILLS")):
            self.assertEqual(_define(sort, c_name), _define(harness, h_name), c_name)

    def test_the_rule_is_the_later_games(self):
        """Ascending key, index tie-break, position kept across a mode change."""
        sort = SORT_C.read_text(encoding="utf-8")
        self.assertIn("while (j > 0 && keys[j - 1] > key)", sort, "strictly greater: equal keys keep index order")
        self.assertIn("the position is kept, as in the later games", sort)
        harness = HARNESS_C.read_text(encoding="utf-8")
        self.assertIn("changing the order keeps the position, as in the later games", harness)
        self.assertIn("switched to Skill without moving: next press shows skill position 3", harness)
        # the selection the game clears before the hook is taken from the last drawn frame
        self.assertIn("if (current < 0) {\n        current = g_seen_selection;", sort)


class StockExecutableFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pe = pefile.PE(str(STOCK))
        cls.image, cls.base = bytes(pe.get_memory_mapped_image()), pe.OPTIONAL_HEADER.ImageBase

    def at(self, va, n):
        return self.image[va - self.base:va - self.base + n]

    def test_the_two_arrow_stores_and_their_hooks(self):
        # right arrow: the search loop ends in `mov [eax+0xAD34], edi`; left: `mov [ecx+0xAD34], edi`
        self.assertEqual(self.at(0x44A7FF, 6), bytes.fromhex("89B834AD0000"))
        self.assertEqual(self.at(0x44A8B4, 6), bytes.fromhex("89B934AD0000"))
        # the stock walk tests occupied (+0x28) and health (+0x344) > 0
        self.assertEqual(self.at(0x44A7CF, 5), bytes.fromhex("8A5028" + "84D2"))
        self.assertEqual(self.at(0x44A7D6, 8), bytes.fromhex("8B9044030000" + "85D2"))
        # 0x4393E0 clears the selection right before the store: the reason for g_seen_selection
        self.assertEqual(self.at(0x44A7F7, 5), b"\xE8" + (0x4393E0 - 0x44A7FC).to_bytes(4, "little", signed=True))
        self.assertIn(bytes.fromhex("34AD0000FFFFFFFF"), self.at(0x4393E0, 0x20), "0x4393E0 writes -1 to +0xAD34")
        origins = json.loads(ORIGINS_MANIFEST.read_text(encoding="utf-8"))
        by_offset = {int(p["offset"], 16): p for p in origins["patches"]}
        for splice, guard, stub_off, stub_va, direction in (
            (0x4A7FF, "89B834AD0000", 0x8E4A0, 0x4904A0, 1), (0x4A8B4, "89B934AD0000", 0x8E500, 0x490500, -1)):
            self.assertEqual(by_offset[splice]["before"].upper(), guard)
            after = bytes.fromhex(by_offset[splice]["after"])
            self.assertEqual(after, b"\xE9" + (stub_va - (0x400000 + splice) - 5).to_bytes(4, "little", signed=True) + b"\x90")
            stub = bytes.fromhex(by_offset[stub_off]["after"])
            self.assertEqual(stub[0], 0x60, "pushad")
            self.assertIn(b"\x6A" + (direction & 0xFF).to_bytes(1, "little") + b"\x57\xFF\xD0\x89\x04\x24", stub,
                          "push direction; push edi; call eax; mov [esp], eax")
            tail = stub.index(b"\x61")
            self.assertEqual(stub[tail + 1:tail + 7], bytes.fromhex(guard), "the displaced store after popad")
            self.assertEqual(stub[tail + 7:tail + 12], b"\xE9" + ((0x400000 + splice + 6) - (stub_va + tail + 12)).to_bytes(4, "little", signed=True))
        self.assertEqual(bytes.fromhex(by_offset[0x8E560]["after"]), b"Vv1SortStep\0")

    def test_no_inline_asm_operand_is_a_register_name(self):
        source = SORT_C.read_text(encoding="utf-8")
        registers = {"ax", "bx", "cx", "dx", "si", "di", "sp", "bp", "al", "bl", "cl", "dl", "ah", "bh", "ch", "dh"}
        for block in re.findall(r"__asm\s*\{(.*?)\}", source, re.S):
            for line in block.splitlines():
                line = line.split("/*")[0].strip()
                if line.startswith("push "):
                    self.assertNotIn(line[5:].strip(), registers, line)


class WiringTests(unittest.TestCase):
    def test_registered_bundled_documented(self):
        patcher = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('SORT_BY_FEATURE_PATHS = (ROOT / "data" / "vv1_sort_by_feature.json",)', patcher)
        self.assertIn("for feature_path in SORT_BY_FEATURE_PATHS:", patcher)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/sort_by/VVFP VV1 Sort By.dll",', release)
        for name in ART:
            self.assertIn('"assets/sort_by/%s",' % name, release)
        self.assertIn('"data/vv1_sort_by_feature.json",', release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("**Sort by Age/Skill/Health in Details Screen**", readme)
        self.assertIn("- Patch ID: `vv1_sort_by`", readme)
        how = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        self.assertIn("SORT BY AGE/SKILL/HEALTH IN DETAILS SCREEN (A NEW HOME)", how)

    def test_the_row_is_public(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher  # noqa: E402

        rows = {f.id: f for f in vv_fun_patcher.load_public_fun_patches()}
        self.assertIn("vv1_sort_by", rows)
        self.assertEqual(rows["vv1_sort_by"].name, "Sort by Age/Skill/Health in Details Screen")


if __name__ == "__main__":
    unittest.main()
