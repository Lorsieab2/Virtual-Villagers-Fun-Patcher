"""The logs name each villager's special title, by the game's own rule.

The owner (2026-10-06): "in the logs please signify 'Special Villagers'
(tribal chief, esteemed elder, scholar, retired chief, golden child etc
etc)".  native/shared/special_title.h holds each game's Details-panel title
rule; the Village History / Village Population roster and every Deaths,
Disappeared, Arrived and Unaccounted record print it as "Special villager:".

The rules are compiled into a tiny DLL here and run on hand-made records, so
the test reads no game file.
"""
from __future__ import annotations

import ctypes
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "native/shared/special_title.h"

SOURCE = r'''
#include "special_title.h"
__declspec(dllexport) const char *Title(int game, const unsigned char *record) {
    return vv_special_title(game, record);
}
__declspec(dllexport) const char *TitleFormer(int game, const unsigned char *record, int former) {
    return vv_special_title_former(game, record, former);
}
'''


def _build(folder: Path) -> Path | None:
    name = "vcvars32.bat" if struct.calcsize("P") == 4 else "vcvars64.bat"
    vcvars = None
    for base in (r"C:\Program Files\Microsoft Visual Studio", r"C:\Program Files (x86)\Microsoft Visual Studio"):
        for candidate in sorted(Path(base).glob(f"*/*/VC/Auxiliary/Build/{name}")):
            vcvars = candidate
    if vcvars is None:
        return None
    (folder / "t.c").write_text(SOURCE, encoding="utf-8")
    command = (f'call "{vcvars}" >nul && cl /nologo /LD /O2 /I "{HEADER.parent}" t.c '
               f'/Fe:t.dll /link /NOLOGO >nul')
    result = subprocess.run(command, shell=True, cwd=folder, capture_output=True, text=True)
    return folder / "t.dll" if result.returncode == 0 and (folder / "t.dll").is_file() else None


class SpecialTitleRules(unittest.TestCase):
    """The rules as the exe's Details panel applies them (static analysis
    addresses in the header)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        dll = _build(Path(cls._tmp))
        if dll is None:
            raise unittest.SkipTest("needs the Visual C++ tools")
        cls.dll = ctypes.CDLL(str(dll))
        cls.dll.Title.restype = ctypes.c_char_p
        cls.dll.Title.argtypes = [ctypes.c_int, ctypes.c_char_p]
        cls.dll.TitleFormer.restype = ctypes.c_char_p
        cls.dll.TitleFormer.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def title(self, game: int, record: bytearray):
        value = self.dll.Title(game, bytes(record))
        return value.decode() if value else None

    def test_a_new_home_golden_child(self):
        r = bytearray(0x3D8)
        self.assertIsNone(self.title(1, r))
        struct.pack_into("<i", r, 0x36C, 0xC7)
        self.assertEqual(self.title(1, r), "Golden Child")

    def test_the_lost_children_esteemed_elder(self):
        r = bytearray(0x800)
        self.assertIsNone(self.title(2, r))
        r[0x7FC] = 1
        self.assertEqual(self.title(2, r), "Esteemed Elder")

    def test_the_secret_city_chief_first_then_three_mastered_skills(self):
        r = bytearray(0x1000)
        struct.pack_into("<5i", r, 0xEAC, 88, 88, 87, 0, 0)
        self.assertIsNone(self.title(3, r))
        struct.pack_into("<5i", r, 0xEAC, 88, 88, 88, 0, 0)
        self.assertEqual(self.title(3, r), "Esteemed Elder")
        r[0xE80] = 1
        self.assertEqual(self.title(3, r), "Tribal Chief")

    def test_the_tree_of_life_scholar_needs_all_five(self):
        r = bytearray(0x2000)
        struct.pack_into("<5f", r, 0x1C5C, 88, 88, 88, 88, 87.9)
        self.assertIsNone(self.title(4, r))
        struct.pack_into("<5f", r, 0x1C5C, 88, 88, 88, 88, 88)
        self.assertEqual(self.title(4, r), "Scholar")

    def former(self, game: int, record: bytearray, kind: int):
        value = self.dll.TitleFormer(game, bytes(record), kind)
        return value.decode() if value else None

    def test_new_believers(self):
        r = bytearray(0x2000)
        self.assertIsNone(self.title(5, r))
        struct.pack_into("<6f", r, 0x1C5C, 88, 88, 88, 0, 0, 0)
        self.assertEqual(self.title(5, r), "Esteemed Elder")
        # A believer still of role 13: the conversion keeps 13 only for the
        # Heathen Chief (0x466966).
        struct.pack_into("<i", r, 0x1CFC, 13)
        self.assertEqual(self.title(5, r), "Retired Heathen Chief")
        struct.pack_into("<i", r, 0x1CFC, 0)
        # Converted Heathens: the Former Heathens file's mask, else the mask
        # bytes the conversion leaves.
        for kind, words in ((0, "Former Heathen (blue mask)"), (1, "Former Heathen (orange mask)"),
                            (2, "Former Heathen (red mask)"), (3, "Former Heathen Master (purple mask)"),
                            (4, "Retired Heathen Chief")):
            with self.subTest(kind=kind):
                self.assertEqual(self.former(5, r, kind), words)
        self.assertEqual(self.former(5, r, -1), "Esteemed Elder", "no entry: the skill title")
        r[0x1CEE] = 1
        self.assertEqual(self.title(5, r), "Former Heathen (red mask)")
        r[0x1CED] = 1
        self.assertEqual(self.title(5, r), "Former Heathen (orange mask)")
        r[0x1CED] = r[0x1CEE] = 0
        self.assertEqual(self.former(1, bytearray(0x3D8), 2), None, "only New Believers has Heathens")
        r[0x1CEC] = 1
        for role, words in ((12, "Heathen Doctor"), (13, "Heathen Chief"),
                            (14, "Heathen Master Scientist"), (15, "Heathen Master Builder"),
                            (16, "Heathen Master Farmer"), (17, "Heathen Mommy")):
            struct.pack_into("<i", r, 0x1CFC, role)
            with self.subTest(role=role):
                self.assertEqual(self.title(5, r), words)
        struct.pack_into("<i", r, 0x1CFC, 3)
        self.assertEqual(self.title(5, r), "Esteemed Elder", "another Heathen: the skill title")


STAND_IN = r'''
#include <windows.h>
static int installed = 1;
__declspec(dllexport) int __stdcall VvfpEsteemedEldersInstalled(void) { return installed; }
__declspec(dllexport) void SetInstalled(int value) { installed = value; }
'''


class EsteemedEldersInEveryGame(unittest.TestCase):
    """The owner (2026-11-22): with "Esteemed Elders in Every Game" in the game, the logs' Special villager line
    follows its title -- three or more skills at the game's Master level in A New Home (90), The Lost Children and
    The Tree of Life (88; three or four there, all five being the Scholar) -- never the Golden Child, a totem statue
    or a ghost.  Without the row (its companion not loaded, or loaded but not installed) nothing changes.  The
    companion is stood in for by a DLL of its name answering VvfpEsteemedEldersInstalled."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        folder = Path(cls._tmp)
        dll = _build(folder)
        if dll is None:
            raise unittest.SkipTest("needs the Visual C++ tools")
        name = "vcvars32.bat" if struct.calcsize("P") == 4 else "vcvars64.bat"
        vcvars = None
        for base in (r"C:\Program Files\Microsoft Visual Studio", r"C:\Program Files (x86)\Microsoft Visual Studio"):
            for candidate in sorted(Path(base).glob(f"*/*/VC/Auxiliary/Build/{name}")):
                vcvars = candidate
        (folder / "elders.c").write_text(STAND_IN, encoding="utf-8")
        subprocess.run(f'call "{vcvars}" >nul && cl /nologo /LD elders.c "/Fe:VVFP Esteemed Elders.dll" '
                       '/link /NOLOGO >nul', shell=True, cwd=folder, capture_output=True, text=True)
        cls.dll = ctypes.CDLL(str(dll))
        cls.dll.Title.restype = ctypes.c_char_p
        cls.dll.Title.argtypes = [ctypes.c_int, ctypes.c_char_p]
        cls.stand_in_path = folder / "VVFP Esteemed Elders.dll"
        cls.stand_in = None

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.stand_in is not None:
            ctypes.windll.kernel32.FreeLibrary(ctypes.c_void_p(cls.stand_in._handle))
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def title(self, game: int, record: bytearray):
        value = self.dll.Title(game, bytes(record))
        return value.decode() if value else None

    def records(self):
        vv1 = bytearray(0x3D8)
        struct.pack_into("<5i", vv1, 0x3BC, 90, 95, 100, 10, 0)
        vv2 = bytearray(0x800)
        struct.pack_into("<5i", vv2, 0x7E4, 88, 88, 88, 0, 0)
        vv4 = bytearray(0x2000)
        struct.pack_into("<5f", vv4, 0x1C5C, 88, 90, 100, 87.9, 0)
        return vv1, vv2, vv4

    def test_without_the_row_the_stock_titles(self):
        """Before (and without the companion): no title for these villagers."""
        if type(self).stand_in is not None:
            self.skipTest("the stand-in is loaded in this process already")
        vv1, vv2, vv4 = self.records()
        self.assertIsNone(self.title(1, vv1))
        self.assertIsNone(self.title(2, vv2))
        self.assertIsNone(self.title(4, vv4))
        self.assertEqual(self.title(5, self.heathen()), "Esteemed Elder", "the stock panel's rule titles a Heathen")

    def heathen(self, faction=1, orange=0):
        r = bytearray(0x2000)
        struct.pack_into("<6f", r, 0x1C5C, 88, 90, 100, 0, 0, 0)
        r[0x1CEC], r[0x1CED] = faction, orange
        struct.pack_into("<i", r, 0x1CFC, 3)
        return r

    def test_with_the_row(self):
        if not self.stand_in_path.is_file():
            self.skipTest("the stand-in companion could not be built")
        self.test_without_the_row_the_stock_titles()
        type(self).stand_in = ctypes.CDLL(str(self.stand_in_path))
        vv1, vv2, vv4 = self.records()
        self.assertEqual(self.title(1, vv1), "Esteemed Elder")
        self.assertEqual(self.title(2, vv2), "Esteemed Elder")
        self.assertEqual(self.title(4, vv4), "Esteemed Elder")
        struct.pack_into("<i", vv1, 0x3BC + 8, 89)
        self.assertIsNone(self.title(1, vv1), "89 is not a Master in A New Home")
        struct.pack_into("<i", vv1, 0x3BC + 8, 100)
        struct.pack_into("<i", vv1, 0x36C, 0xC7)
        self.assertEqual(self.title(1, vv1), "Golden Child")
        vv2[0x558] = 1
        self.assertIsNone(self.title(2, vv2), "never a totem statue")
        vv2[0x558] = 0
        struct.pack_into("<5f", vv4, 0x1C5C, 88, 88, 88, 88, 88)
        self.assertEqual(self.title(4, vv4), "Scholar")
        vv4b = bytearray(0x2000)
        struct.pack_into("<5f", vv4b, 0x1C5C, 88, 90, 100, 0, 0)
        vv4b[0x1CC7] = 1
        self.assertIsNone(self.title(4, vv4b), "never a ghost")
        # Loaded but not installed (its sites refused): the stock titles.
        # New Believers (the owner, 2026-11-22): a current Heathen never; a believer yes; a Former Heathen keeps the
        # Former Heathen title in the logs (the priority list).
        self.assertIsNone(self.title(5, self.heathen()), "a current Heathen is never an Esteemed Elder")
        self.assertEqual(self.title(5, self.heathen(faction=0)), "Esteemed Elder")
        self.assertEqual(self.title(5, self.heathen(faction=0, orange=1)), "Former Heathen (orange mask)")
        self.stand_in.SetInstalled(0)
        self.assertEqual(self.title(5, self.heathen()), "Esteemed Elder", "not installed: the stock rule")
        vv1, vv2, vv4 = self.records()
        self.assertIsNone(self.title(1, vv1))
        self.assertIsNone(self.title(2, vv2))
        self.stand_in.SetInstalled(1)

class TheLogsPrintIt(unittest.TestCase):
    def test_both_exporters_print_the_line(self):
        population = (ROOT / "native/population_export/population_export.c").read_text(encoding="utf-8")
        self.assertIn('"  Special villager: %s\\n", special', population)
        parentage = (ROOT / "native/parentage_export/parentage_export.c").read_text(encoding="utf-8")
        self.assertIn('"  Special villager: %s\\n",\n                    record_special_title(game_id, g, record)',
                      parentage.replace("\r\n", "\n"))
        # Both read New Believers' Former Heathens file for the slot.
        self.assertIn("vv_former_load(slot, g_former)", population)
        # ...the parentage companion for the slot the game has loaded, never the header published last
        # (which still names the village saved last after another is loaded).
        self.assertIn("vv_former_load(village_files_slot(game_id), former)", parentage)
        self.assertNotIn("vv_former_load(vv_former_header_slot(village), former)", parentage)

    def test_a_former_heathen_identity_two_villagers_share_is_nobodys(self):
        # Codex (#553): the Former Heathens file keys a villager by name, likes and
        # dislikes; when two living villagers carry one key, neither is named a
        # Former Heathen.
        population = (ROOT / "native/population_export/population_export.c").read_text(encoding="utf-8")
        self.assertIn("drop_ambiguous_former(g, villagers);", population)
        parentage = (ROOT / "native/parentage_export/parentage_export.c").read_text(encoding="utf-8")
        self.assertIn("if (carriers > 0) {", parentage)
        # A rebuilt (departed) record's custom title: any present carrier is a collision
        # (a live record's goes by its own index and looks, native/shared/custom_title_shown.h).
        flat = " ".join(parentage.split())
        self.assertIn("so ANY present carrier of its identity may be the title's owner (Codex, #553): then no title.",
                      flat)
        self.assertIn("g->preference_slots) == identity) { return 0; }", flat)
        self.assertIn("if (!vv_title_shown_on(&titles[i], &table, r)) {", parentage)
        self.assertIn("record_custom_title(game_id, g, record, live, !check, custom, sizeof custom);", parentage)

    def test_the_shipped_dlls_carry_it(self):
        for dll in ("assets/population/VVFP Population Export.dll",
                    "assets/parentage/VVFP Parentage Export.dll"):
            blob = (ROOT / dll).read_bytes()
            with self.subTest(dll=dll):
                self.assertIn(b"  Special villager: %s\n", blob)
                self.assertIn(b"Heathen Master Scientist", blob)
                self.assertIn(b"Scholar", blob)


if __name__ == "__main__":
    unittest.main()
