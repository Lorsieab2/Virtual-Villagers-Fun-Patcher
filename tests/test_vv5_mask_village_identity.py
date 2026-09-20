"""The VV5 mask sidecar's village identity is the living roster.

v1.35.13 bound the file to two dwords read at 0x4DBFC8+8+0x328/+0x338, on
the belief that 0x4DBFC8+8 was the save buffer.  It is not.  The save routine
at 0x4244F0 is a __thiscall on a save-state object that GATHERS the static
managers into the buffer, and 0x4DBFC8 (the collectible manager) lands at
+0x640; +0x328 is the trophy-progress table at 0x4DB358.  Read live those two
dwords were zero, so WriteMaskSidecar refused every write and no file was
ever created: the owner's "masks are not persistent in the latest vv5 modded".
And the object it meant to read is a statistics table whose values move
during play, so it could never have been an identity anyway.

The identity that works, proven in The Lost Children, is the living villager
roster compared on a strict majority.  These guards pin that design in the
DLL and in the appended page, derive every record offset from the population
exporter's table rather than restating it, and confirm the built DLL carries
the new format.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

SOURCE = ROOT / "native" / "vv5_task9_origins" / "vv5_task9_origins.c"
DEF = ROOT / "native" / "vv5_task9_origins" / "vv5_task9_origins.def"
BUILDER = ROOT / "scripts" / "build_vv5_task9_native_actions.py"
DLL = ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll"
POPULATION = ROOT / "native" / "population_export" / "population_export.c"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"

MAGIC = 0x35304D56          # 'VM05'
OLD_TAGGED_MAGIC = 0x31304D56   # 'VM01', v1.35.13's never-written format
WRONG_TAG_A = 0x4DBFC8 + 8 + 0x328
WRONG_TAG_B = 0x4DBFC8 + 8 + 0x338


def _population_vv5_row() -> dict:
    """The exporter's VV5 layout row: the one parser review already hardened."""
    text = POPULATION.read_text(encoding="utf-8")
    start = text.index("/* VV5 -- New Believers.")
    body = text[start:text.index("}", start)]
    nums = [int(x, 16) if x.lower().startswith("0x") else int(x)
            for x in re.findall(r"\b(0x[0-9A-Fa-f]+|\d+)u?\b", body)]
    # struct game_layout order: supported, rva, is_pointer, record_base,
    # stride, slots, active, age, head, body, name, name_capacity, ...
    return {
        "rva": nums[1], "is_pointer": nums[2], "record_base": nums[3],
        "stride": nums[4], "slots": nums[5], "active": nums[6],
        "name": nums[10], "name_capacity": nums[11],
    }


class Vv5RosterIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SOURCE.read_text(encoding="utf-8")
        self.builder = BUILDER.read_text(encoding="utf-8")

    def _macro(self, name: str) -> int:
        match = re.search(r"^#define\s+%s\s+\(?(0x[0-9A-Fa-f]+|\d+)u?" % re.escape(name),
                          self.text, re.MULTILINE)
        self.assertIsNotNone(match, "%s is not defined" % name)
        return int(match.group(1), 0)

    def _function(self, signature_start: str) -> str:
        start = self.text.index(signature_start)
        depth = 0
        for index in range(start, len(self.text)):
            if self.text[index] == "{":
                depth += 1
            elif self.text[index] == "}":
                depth -= 1
                if depth == 0:
                    return self.text[start:index + 1]
        self.fail("unterminated " + signature_start)

    # -- the wrong identity is gone ------------------------------------------------

    def test_the_manager_plus_eight_tag_is_gone_everywhere(self) -> None:
        for text, where in ((self.text, "DLL"), (self.builder, "builder")):
            self.assertNotIn("VV5_MANAGER", text, where)
            self.assertNotIn("vv5_village_tag", text, where)
            self.assertNotIn("VV5_TAG_A", text, where)
            # the diagnosis may cite 0x4DBFC8 in prose; no CODE may read it
            self.assertNotRegex(text, r"\(UINT_PTR\)\s*\(?\s*(VV5_MANAGER|0x0*4DBFC8)", where)
        self.assertNotIn("%#X" % WRONG_TAG_A, self.builder.upper())
        self.assertNotIn("%#X" % WRONG_TAG_B, self.builder.upper())

    def test_stock_save_routine_confirms_the_diagnosis(self) -> None:
        """Positive control on the executable: buffer+0x328 is gathered from
        0x4DB358 and the collectible manager 0x4DBFC8 lands at +0x640."""
        if not STOCK.is_file():
            self.skipTest("stock VV5 executable not present")
        blob = STOCK.read_bytes()
        gather_328 = (b"\x8d\x86\x28\x03\x00\x00"       # lea eax, [esi+0x328]
                      b"\x50"                            # push eax
                      b"\xb9\x58\xb3\x4d\x00")           # mov ecx, 0x4DB358
        gather_640 = (b"\x8d\x8e\x40\x06\x00\x00"       # lea ecx, [esi+0x640]
                      b"\x51"                            # push ecx
                      b"\xb9\xc8\xbf\x4d\x00")           # mov ecx, 0x4DBFC8
        self.assertEqual(blob.count(gather_328), 1, "buffer+0x328 is what 0x4DB358 serialises")
        self.assertEqual(blob.count(gather_640), 1, "0x4DBFC8 serialises into buffer+0x640, not +0x328")
        villagers = b"\x8d\x8e\x0c\xc9\x00\x00\x51\xb9\x48\x41\x55\x00"  # lea ecx,[esi+0xc90c]; push ecx; mov ecx,0x554148
        self.assertEqual(blob.count(villagers), 1, "the villager array 0x554148 is gathered into buffer+0xC90C")

    # -- the record layout is the exporter's, not a restatement ------------------

    def test_roster_reads_the_records_the_population_exporter_reads(self) -> None:
        row = _population_vv5_row()
        self.assertEqual(row["is_pointer"], 0, "VV5's RVA is the array itself")
        self.assertEqual(self._macro("VV5_VILLAGERS_VA"), 0x400000 + row["rva"])
        records = re.search(r"#define VV5_ROSTER_RECORDS\s+\(VV5_VILLAGERS_VA \+ (0x[0-9A-Fa-f]+)u\)", self.text)
        self.assertIsNotNone(records)
        self.assertEqual(int(records.group(1), 16), row["record_base"])
        self.assertEqual(self._macro("VV5_ROSTER_STRIDE"), row["stride"])
        self.assertEqual(self._macro("VV5_RECORD_COUNT"), row["slots"])
        self.assertEqual(self._macro("VV5_ACTIVE_OFFSET"), row["active"])
        self.assertEqual(self._macro("VV5_NAME_OFFSET"), row["name"])
        self.assertEqual(self._macro("VV5_NAME_CAPACITY"), row["name_capacity"])
        # and agrees with the barrel-capacity check's own absolute base
        self.assertEqual(0x400000 + row["rva"] + row["record_base"], self._macro("VV5_RECORD_BASE"))

    # -- the rule ----------------------------------------------------------------

    def test_same_village_is_a_strict_majority_of_the_smaller_roster(self) -> None:
        same = self._function("static int vv5_roster_same(")
        self.assertRegex(same, r"need\s*=\s*need\s*/\s*2\s*\+\s*1\s*;")
        self.assertNotRegex(same, r"\(\s*need\s*\+\s*1\s*\)\s*/\s*2", "half is not a majority for even rosters")
        self.assertIn("return 0;", same.split("need = need / 2 + 1")[0], "an empty roster matches nothing")
        self.assertRegex(same, r"vv5_roster_overlap\(a,\s*b\)\s*>=\s*need")

    def test_snapshot_hashes_only_living_names_with_a_terminator(self) -> None:
        snap = self._function("static int vv5_roster_snapshot(")
        self.assertRegex(snap, r"if\s*\(\s*rec\[VV5_ACTIVE_OFFSET\]\s*==\s*0\s*\)")
        self.assertIn("out[i] = 0;", snap)
        self.assertRegex(snap, r"h\s*=\s*\(h\s*\^\s*0xFFu\)\s*\*\s*16777619u;", "terminator: Tai != Taiga")
        self.assertRegex(snap, r"out\[i\]\s*=\s*h\s*\?\s*h\s*:\s*1u;", "0 is reserved for inactive")

    # -- the file ----------------------------------------------------------------

    def test_sidecar_format_is_magic_roster_table(self) -> None:
        self.assertEqual(self._macro("VV5_MASK_SIDECAR_MAGIC"), MAGIC)
        write = self._function("__declspec(dllexport) void __stdcall WriteMaskSidecar(")
        self.assertLess(write.index("if (!g_vv5_have_roster)"), write.index("CreateFileA"),
                        "an unidentified village must not write a file")
        self.assertRegex(write, r"WriteFile\(h,\s*&magic")
        self.assertRegex(write, r"WriteFile\(h,\s*g_vv5_roster,\s*sizeof\(g_vv5_roster\)")
        self.assertRegex(write, r"WriteFile\(h,\s*table,\s*MASK_TABLE_BYTES")
        load = self._function("static void vv5_mask_sidecar_load(")
        self.assertLess(load.index("memset(table, 0, MASK_TABLE_BYTES)"), load.index("return"),
                        "fail closed: the clear must precede EVERY exit, including a failed path")
        self.assertIn("vv5_roster_same(filesnap, live)", load)
        self.assertNotIn("header[1] != tag", load)

    def test_sync_reloads_only_when_the_village_changed(self) -> None:
        sync = self._function("__declspec(dllexport) int __stdcall Vv5MaskSync(")
        self.assertRegex(sync, r"if\s*\(\s*slot\s*<=\s*0\s*\)\s*\{\s*return 0;")
        self.assertRegex(sync, r"if\s*\(\s*vv5_roster_snapshot\(cur\)\s*==\s*0\s*\)\s*\{\s*return 0;")
        self.assertRegex(sync, r"g_vv5_have_roster\s*&&\s*slot\s*==\s*g_vv5_slot\s*&&\s*vv5_roster_same\(g_vv5_roster,\s*cur\)")
        # a birth or death under the same village re-persists the snapshot
        self.assertRegex(sync, r"if\s*\(\s*!vv5_roster_equal\(g_vv5_roster,\s*cur\)\s*\)\s*\{\s*memcpy\(g_vv5_roster,\s*cur,\s*sizeof\(cur\)\);\s*WriteMaskSidecar\(table\);")
        # a replacement clears and reloads through the roster-checked loader
        self.assertIn("vv5_mask_sidecar_load(table, cur);", sync)
        self.assertLess(sync.index("vv5_mask_sidecar_load(table, cur);"), sync.index("g_vv5_have_roster = 1;"))
        # throttled, but never before the first identification
        self.assertRegex(sync, r"g_vv5_have_roster\s*&&\s*\(now\s*-\s*g_vv5_sync_tick\)\s*<\s*VV5_SYNC_INTERVAL_MS")

    def test_export_is_declared(self) -> None:
        self.assertIn("Vv5MaskSync=_Vv5MaskSync@0", DEF.read_text(encoding="utf-8"))

    # -- the appended page -------------------------------------------------------

    def test_flip_asks_the_companion_instead_of_comparing_a_tag(self) -> None:
        flip = self.builder[self.builder.index('put(page, page_va, "mask_flip"'):]
        flip = flip[:flip.index('""")', flip.index('f"""'))]
        self.assertIn("call 0x{page_va + OFF['mask_sync']:X}", flip)
        self.assertNotIn("mask_load_once", flip, "the load-once gate is the companion's decision now")
        self.assertNotIn("xor eax, edx", flip)
        sync = self.builder[self.builder.index('put(page, page_va, "mask_sync"'):]
        sync = sync[:sync.index('""")', sync.index('f"""'))]
        for needle in ("push ecx", "pop ecx", "call dword ptr [0x4951E0]", "call dword ptr [0x4951DC]",
                       "s['sync_export']", "call eax", "mov dword ptr [0x{MASK_LOADED:X}], 1"):
            self.assertIn(needle, sync, needle)
        self.assertIn('("sync_export", b"Vv5MaskSync\\0")', self.builder)
        self.assertRegex(self.builder, r'"mask_sync": 0x6FA0,')
        self.assertRegex(self.builder, r'"mask_sync": 0x60,')

    # -- the artifact ------------------------------------------------------------

    def test_shipped_dll_carries_the_roster_format(self) -> None:
        self.assertTrue(DLL.is_file())
        blob = DLL.read_bytes()
        self.assertIn(struct.pack("<I", MAGIC), blob, "built DLL lacks the 'VM05' magic")
        self.assertNotIn(struct.pack("<I", OLD_TAGGED_MAGIC), blob, "built DLL still carries 'VM01': not rebuilt")
        self.assertIn(b"Vv5MaskSync\0", blob, "built DLL does not export Vv5MaskSync")
        self.assertNotIn(struct.pack("<I", WRONG_TAG_A), blob, "built DLL still reads the wrong tag address")
        self.assertIn(struct.pack("<I", 0x554148 + 0x48), blob, "built DLL does not address the villager records")


if __name__ == "__main__":
    unittest.main()
