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

    def test_new_believers(self):
        r = bytearray(0x2000)
        self.assertIsNone(self.title(5, r))
        struct.pack_into("<6f", r, 0x1C5C, 88, 88, 88, 0, 0, 0)
        self.assertEqual(self.title(5, r), "Esteemed Elder")
        struct.pack_into("<i", r, 0x1CFC, 13)
        # The Retired Chief's puzzle progress is not readable outside the game:
        # never claimed then.
        self.assertEqual(self.title(5, r), "Esteemed Elder")
        r[0x1CEC] = 1
        for role, words in ((12, "Heathen Doctor"), (13, "Heathen Chief"),
                            (14, "Heathen Master Scientist"), (15, "Heathen Master Builder"),
                            (16, "Heathen Master Farmer"), (17, "Heathen Mommy")):
            struct.pack_into("<i", r, 0x1CFC, role)
            with self.subTest(role=role):
                self.assertEqual(self.title(5, r), words)
        struct.pack_into("<i", r, 0x1CFC, 3)
        self.assertEqual(self.title(5, r), "Esteemed Elder", "another Heathen: the skill title")


class TheLogsPrintIt(unittest.TestCase):
    def test_both_exporters_print_the_line(self):
        population = (ROOT / "native/population_export/population_export.c").read_text(encoding="utf-8")
        self.assertIn('"  Special villager: %s\\n", special', population)
        parentage = (ROOT / "native/parentage_export/parentage_export.c").read_text(encoding="utf-8")
        self.assertIn('"  Special villager: %s\\n",\n                    vv_special_title(game_id, record)',
                      parentage.replace("\r\n", "\n"))

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
