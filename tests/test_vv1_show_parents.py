"""Show Parents in Details Screen (A New Home): the companion, its manifest, its
bridges, and the game facts the renderer is built on.

The companion "VVFP VV1 Parentage.dll" keeps every villager's parents in a
sidecar and draws them in the Details portrait.  Its runtime behaviour is
exercised by native/vv1_parentage/vv1_parentage_harness.c (32-bit, loads the
built DLL); this file pins what Python can check: that the shipped DLL is the
one the manifest names, that the DLL exports what the three bridging DLLs
call, that the offsets the companion reads agree with the population
exporter's measured VV1 row, that the executable really has the draw sites
and constants the renderer replays, and that the feature is wired into the
patcher, the release bundle and the documentation.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
DLL = ROOT / "assets" / "parentage" / "VVFP VV1 Parentage.dll"
MANIFEST = ROOT / "data" / "vv1_show_parents_feature.json"
PARENTAGE_C = ROOT / "native" / "vv1_parentage" / "vv1_parentage.c"
HARNESS_C = ROOT / "native" / "vv1_parentage" / "vv1_parentage_harness.c"
ORIGINS_C = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
EXPORT_C = ROOT / "native" / "parentage_export" / "parentage_export.c"
POPULATION_C = ROOT / "native" / "population_export" / "population_export.c"

GAME_EXPORTS = (
    "Vv1ParentageConceived",
    "Vv1ParentageTick",
    "Vv1ParentageDrawPortrait",
    "Vv1ParentageQuery",
    "Vv1ParentageQueryNames",
)


def _define(source: str, name: str) -> int:
    match = re.search(r"#define\s+%s\s+(0x[0-9A-Fa-f]+|\d+)" % re.escape(name), source)
    assert match, name
    return int(match.group(1), 0)


def _stock() -> tuple[bytes, int]:
    pe = pefile.PE(str(STOCK))
    return bytes(pe.get_memory_mapped_image()), pe.OPTIONAL_HEADER.ImageBase


class ManifestAndDllTests(unittest.TestCase):
    def test_manifest_pins_the_shipped_dll(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        files = manifest["companion_files"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["destination"], "VVFP VV1 Parentage.dll")
        self.assertEqual(files[0]["sha256"].upper(), digest)
        self.assertEqual(manifest["patches"], [], "the row changes no executable bytes")
        self.assertEqual(manifest["dependencies"], ["vv1_enable_origins_exclusive_features"])
        self.assertTrue(manifest["enabled"])

    def test_dll_exports_what_the_bridges_call(self):
        pe = pefile.PE(str(DLL))
        names = {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        for export in GAME_EXPORTS:
            self.assertIn(export, names)
        self.assertEqual(pe.FILE_HEADER.Machine, 0x14C, "32-bit, like the game")
        # the DLL must never touch the sidecar from DllMain: only kernel32/user32/shell32
        imports = {entry.dll.decode().lower() for entry in pe.DIRECTORY_ENTRY_IMPORT}
        self.assertTrue(imports <= {"kernel32.dll", "user32.dll", "shell32.dll"}, imports)

    def test_each_bridge_asks_for_an_export_that_exists(self):
        origins = ORIGINS_C.read_text(encoding="utf-8")
        export = EXPORT_C.read_text(encoding="utf-8")
        population = POPULATION_C.read_text(encoding="utf-8")
        for source, exports in (
            (origins, ("Vv1ParentageTick", "Vv1ParentageDrawPortrait")),
            (export, ("Vv1ParentageConceived",)),
            (population, ("Vv1ParentageQuery", "Vv1ParentageQueryNames")),
        ):
            self.assertIn('"VVFP VV1 Parentage.dll"', source)
            for name in exports:
                self.assertIn('GetProcAddress(companion, "%s")' % name, source)
        # the per-frame tick and the portrait draw are both wired in
        self.assertIn("vv1_parentage_bridge_tick();", origins)
        self.assertIn("vv1_parentage_bridge_draw(gameobj, record, draw_wrapper, args);", origins)
        # the conception bridge fires only with a validated father in hand
        self.assertIn("vv1_parentage_bridge(records, mother, father);", export)
        # the birth record the companion writes lives in the log's owner
        self.assertIn("__stdcall WriteParentageBirth(", export)
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(companion, "WriteParentageBirth")', parentage)
        # the roster block
        self.assertIn("write_vv1_own_parents(file, index)", population)
        # ...and it must be exported under the name the companion asks for
        export_dll = pefile.PE(str(ROOT / "assets" / "parentage" / "VVFP Parentage Export.dll"))
        exported = {e.name.decode() for e in export_dll.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.assertIn("WriteParentageBirth", exported)


class OffsetAgreementTests(unittest.TestCase):
    """The companion reads the same VV1 record geometry the exporter measured."""

    def test_record_geometry_matches_the_population_exporter(self):
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        population = POPULATION_C.read_text(encoding="utf-8")
        # the exporter's VV1 row: villagers_rva, indirect, record_base, stride, slots,
        # active, age, head, body, name, name_capacity
        row = re.search(
            r"\{\s*1,\s*0x8B614u,\s*1,\s*(0x[0-9A-Fa-f]+|\d+)u,\s*(0x[0-9A-Fa-f]+)u,\s*(\d+)u,\s*"
            r"(0x[0-9A-Fa-f]+)u,\s*(0x[0-9A-Fa-f]+)u,\s*(0x[0-9A-Fa-f]+)u,\s*(0x[0-9A-Fa-f]+)u,\s*"
            r"(0x[0-9A-Fa-f]+)u,\s*(0x[0-9A-Fa-f]+)u",
            population,
        )
        self.assertIsNotNone(row, "the exporter's VV1 layout row")
        record_base, stride, slots, active, age, head, body, name, name_cap = (int(v, 0) for v in row.groups())
        self.assertEqual(_define(parentage, "VV1_RECORDS_OFFSET"), record_base)
        self.assertEqual(_define(parentage, "VV1_RECORD_STRIDE"), stride)
        self.assertEqual(_define(parentage, "VV1_RECORD_COUNT"), slots)
        self.assertEqual(_define(parentage, "VV1_OCCUPIED_OFFSET"), active)
        self.assertEqual(_define(parentage, "VV1_AGE_OFFSET"), age)
        self.assertEqual(_define(parentage, "VV1_HEAD_OFFSET"), head)
        self.assertEqual(_define(parentage, "VV1_BODY_OFFSET"), body)
        self.assertEqual(_define(parentage, "VV1_NAME_OFFSET"), name)
        self.assertEqual(_define(parentage, "VV1_NAME_CAPACITY"), name_cap)

    def test_the_harness_uses_the_same_layout(self):
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        harness = HARNESS_C.read_text(encoding="utf-8")
        for c_name, h_name in (
            ("VV1_RECORD_STRIDE", "STRIDE"), ("VV1_RECORD_COUNT", "COUNT"), ("VV1_OCCUPIED_OFFSET", "OCC"),
            ("VV1_AGE_OFFSET", "AGE"), ("VV1_LITTER_OFFSET", "LITTER"), ("VV1_HEAD_OFFSET", "HEAD"),
            ("VV1_BODY_OFFSET", "BODY"), ("VV1_VARIANT_OFFSET", "VARIANT"), ("VV1_NAME_OFFSET", "NAME"),
        ):
            self.assertEqual(_define(parentage, c_name), _define(harness, h_name), c_name)
        # 8 bytes of appearance plus three 28-byte names: what the harness pins as 92
        entry = 8 + 3 * _define(parentage, "VV1_NAME_CAPACITY")
        self.assertEqual(entry, 92)
        self.assertIn("entry_bytes == 92", harness)

    def test_parents_show_under_eighteen_in_the_games_units(self):
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        origins = ORIGINS_C.read_text(encoding="utf-8")
        self.assertEqual(_define(parentage, "VV1_UNITS_PER_YEAR"), 20)
        self.assertIn("20 units is one villager year", origins)
        self.assertEqual(_define(parentage, "VV1_PARENTS_UNTIL_YEARS"), 18)
        self.assertIn("VV1_PARENTS_UNTIL_YEARS * VV1_UNITS_PER_YEAR", parentage)


class StockExecutableFactsTests(unittest.TestCase):
    """What the renderer replays really is in the stock game."""

    @classmethod
    def setUpClass(cls):
        cls.image, cls.base = _stock()

    def at(self, va: int, n: int) -> bytes:
        return self.image[va - self.base:va - self.base + n]

    def test_portrait_draw_sites(self):
        # child body: push 0xFD; push 0x78 then the head: push 0x102; push 0x78
        self.assertEqual(self.at(0x4373C9, 7), bytes.fromhex("68FD0000006A78"))
        self.assertEqual(self.at(0x43740D, 7), bytes.fromhex("68020100006A78"))
        # adult body / head: push 0xE9 / push 0xE4 with push 0x78, scale 0xC8, frame 0xB
        self.assertEqual(self.at(0x4374B1, 7), bytes.fromhex("68C80000006A0B"))
        self.assertEqual(self.at(0x4374CD, 7), bytes.fromhex("68E90000006A78"))
        self.assertEqual(self.at(0x4374FB, 7), bytes.fromhex("68E40000006A78"))
        # the adult threshold: cmp ecx, 0x118
        self.assertEqual(self.at(0x437377, 6), bytes.fromhex("81F918010000"))
        # the scaled draw wrapper dereferences its object and jumps to 0x408AF0
        self.assertEqual(self.at(0x409410, 2), bytes.fromhex("8B09"))
        rel = struct.unpack_from("<i", self.image, 0x409412 - self.base + 1)[0]
        self.assertEqual(0x409412 + 5 + rel, 0x408AF0)
        # ...which passes 1.0f as the blit alpha: push 0x3F800000
        self.assertEqual(self.at(0x408B66, 5), bytes.fromhex("68 00 00 80 3F".replace(" ", "")))
        # and the scale-to-float constant is 0.01
        self.assertAlmostEqual(struct.unpack_from("<f", self.image, 0x457454 - self.base)[0], 0.01, places=6)

    def test_atlas_geometry(self):
        # heads: 7 columns x 20 rows (push 0x14; push 7; push "female_heads.png")
        self.assertEqual(self.at(0x43C08E, 9), bytes.fromhex("6A146A0768F4214800"))
        self.assertEqual(self.image[0x4821F4 - self.base:0x4821F4 - self.base + 16], b"female_heads.png")
        # bodies: 32 columns x 20 rows over a 2x2 sheet grid
        self.assertEqual(self.at(0x43C0FD, 6), bytes.fromhex("6A146A205555"))
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        self.assertEqual(_define(parentage, "VV1_CELL_W"), 280 // 7)
        self.assertEqual(_define(parentage, "VV1_CELL_H"), 1300 // 20)
        self.assertLess(_define(parentage, "VV1_FATHER_HEAD_COL"), 7)
        self.assertLess(_define(parentage, "VV1_MOTHER_HEAD_COL"), 7)
        self.assertLess(_define(parentage, "VV1_FATHER_BODY_COL"), 32)
        self.assertLess(_define(parentage, "VV1_MOTHER_BODY_COL"), 32)

    def test_the_mouse_comes_from_the_games_own_sdl(self):
        pe = pefile.PE(str(STOCK))
        names = {
            i.name.decode()
            for entry in pe.DIRECTORY_ENTRY_IMPORT
            if entry.dll.decode().lower() == "sdl2.dll"
            for i in entry.imports
            if i.name
        }
        self.assertIn("SDL_GetMouseState", names)
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(sdl, "SDL_GetMouseState")', parentage)

    def test_no_inline_asm_operand_is_a_register_name(self):
        """`push cx` pushes the 16-bit register, not a local: that was a crash."""
        parentage = PARENTAGE_C.read_text(encoding="utf-8")
        registers = {"ax", "bx", "cx", "dx", "si", "di", "sp", "bp", "al", "bl", "cl", "dl",
                     "ah", "bh", "ch", "dh", "eax", "ebx", "ecx", "edx", "esi", "edi", "esp", "ebp"}
        for block in re.findall(r"__asm\s*\{(.*?)\}", parentage, re.S):
            for line in block.splitlines():
                line = line.split("/*")[0].strip()
                if line.startswith("push "):
                    operand = line[5:].strip()
                    self.assertNotIn(operand, registers, line)


class WiringTests(unittest.TestCase):
    def test_registered_in_the_patcher_and_the_release(self):
        patcher = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('SHOW_PARENTS_FEATURE_PATHS = (ROOT / "data" / "vv1_show_parents_feature.json",)', patcher)
        self.assertIn("for feature_path in SHOW_PARENTS_FEATURE_PATHS:", patcher)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/parentage/VVFP VV1 Parentage.dll",', release)
        self.assertIn('"data/vv1_show_parents_feature.json",', release)

    def test_the_row_is_public_and_depends_only_on_origins(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        import vv_fun_patcher  # noqa: E402

        rows = {f.id: f for f in vv_fun_patcher.load_public_fun_patches()}
        self.assertIn("vv1_show_parents", rows)
        row = rows["vv1_show_parents"]
        self.assertEqual(row.name, "Show Parents in Details Screen")
        self.assertEqual(row.game_id, "vv1")

    def test_documented(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        how = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        self.assertIn("**Show Parents in Details Screen**", readme)
        self.assertIn("- Patch ID: `vv1_show_parents`", readme)
        self.assertIn("SHOW PARENTS IN DETAILS SCREEN (A NEW HOME)", how)
        self.assertIn("vv1_parents_<slot>.dat      A New Home", how)


if __name__ == "__main__":
    unittest.main()
