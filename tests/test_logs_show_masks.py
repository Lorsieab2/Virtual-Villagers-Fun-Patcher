"""The logs' "Mask:" line (the owner, 2026-10-06: "Mask type" in the villager logs).

native/shared/mask_line.h names the mask a villager wears: New Believers' own
Heathen masks from the record (the game's mask draw, 0x4728C6), and the
patcher's cosmetic Heathen masks from each game's Origins companion, through
the VvfpMaskOf export every companion now carries (native/shared/story_bridge.h).

The header is compiled into a tiny DLL here, beside a stand-in Origins
companion that answers VvfpMaskOf from the record's first byte, so the test
reads no game file.
"""
from __future__ import annotations

import ctypes
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "native" / "shared"

UNDER_TEST = r'''
#include "mask_line.h"
__declspec(dllexport) const char *MaskName(int game, const unsigned char *record) {
    return vv_mask_name(game, record);
}
'''
STAND_IN = r'''
__declspec(dllexport) int __stdcall VvfpMaskOf(void *record) {
    return ((const unsigned char *)record)[0];
}
'''
ORIGINS = {
    1: ROOT / "assets/origins/VVFP VV1 Origins Icons.dll",
    2: ROOT / "assets/origins/VVFP VV2 Origins Icons.dll",
    3: ROOT / "data/candidates/VVFP VV3 Safe Upgrades.dll",
    4: ROOT / "assets/origins/VVFP VV4 Origins Icons.dll",
    5: ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
}


def _vcvars() -> Path | None:
    name = "vcvars32.bat" if struct.calcsize("P") == 4 else "vcvars64.bat"
    found = None
    for base in (r"C:\Program Files\Microsoft Visual Studio", r"C:\Program Files (x86)\Microsoft Visual Studio"):
        for candidate in sorted(Path(base).glob(f"*/*/VC/Auxiliary/Build/{name}")):
            found = candidate
    return found


def _cl(folder: Path, source: str, name: str, out: str, extra: str = "") -> Path | None:
    vcvars = _vcvars()
    if vcvars is None:
        return None
    (folder / name).write_text(source, encoding="utf-8")
    command = (f'call "{vcvars}" >nul && cl /nologo /LD /O2 /I "{SHARED}" "{name}" {extra} '
               f'/Fe:"{out}" /link /NOLOGO >nul')
    result = subprocess.run(command, shell=True, cwd=folder, capture_output=True, text=True)
    return folder / out if result.returncode == 0 and (folder / out).is_file() else None


class MaskLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        folder = Path(cls._tmp)
        dll = _cl(folder, UNDER_TEST, "t.c", "t.dll")
        stand_in = _cl(folder, STAND_IN, "s.c", "VVFP VV2 Origins Icons.dll")
        if dll is None or stand_in is None:
            raise unittest.SkipTest("needs the Visual C++ tools")
        cls.dll = ctypes.CDLL(str(dll))
        cls.dll.MaskName.restype = ctypes.c_char_p
        cls.dll.MaskName.argtypes = [ctypes.c_int, ctypes.c_char_p]
        cls.stand_in_path = stand_in

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def name(self, game: int, record: bytes):
        value = self.dll.MaskName(game, record)
        return value.decode() if value else None

    def test_no_companion_loaded_no_mask(self):
        self.assertIsNone(self.name(4, bytes([3]) + bytes(0x2000)))

    def test_the_companion_names_the_cosmetic_mask(self):
        ctypes.CDLL(str(self.stand_in_path))       # loaded, as the game loads its Origins companion
        for value, words in ((0, None), (1, "Blue Mask"), (2, "Orange Mask"), (3, "Red Mask"),
                             (4, "Purple Mask"), (5, "Tribal Chief Mask"), (6, None)):
            with self.subTest(value=value):
                self.assertEqual(self.name(2, bytes([value]) + bytes(0x1000)), words)

    def test_new_believers_heathens_wear_the_games_own_mask(self):
        def heathen(kind_type=0, orange=0, red=0):
            r = bytearray(0x2000)
            r[0x1CEC] = 1
            r[0x1CED] = orange
            r[0x1CEE] = red
            struct.pack_into("<i", r, 0x1CFC, kind_type)
            return bytes(r)
        self.assertEqual(self.name(5, heathen()), "Blue Mask")
        self.assertEqual(self.name(5, heathen(orange=1)), "Orange Mask")
        self.assertEqual(self.name(5, heathen(red=1)), "Red Mask")
        for master in (12, 14, 15, 16):
            with self.subTest(type=master):
                self.assertEqual(self.name(5, heathen(master)), "Purple Mask")
        self.assertEqual(self.name(5, heathen(13)), "Tribal Chief Mask")
        self.assertEqual(self.name(5, heathen(17, red=1)), "Red Mask", "the Heathen Mommy: her mask bytes")


class EveryOriginsCompanionAnswers(unittest.TestCase):
    def test_vvfpmaskof_is_exported(self):
        for game, path in ORIGINS.items():
            with self.subTest(game=game):
                pe = pefile.PE(str(path))
                names = {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
                self.assertIn(b"VvfpMaskOf", names)

    def test_both_exporters_print_it(self):
        population = (ROOT / "native/population_export/population_export.c").read_text(encoding="utf-8")
        parentage = (ROOT / "native/parentage_export/parentage_export.c").read_text(encoding="utf-8")
        self.assertIn('fprintf(file, "  Mask: %s\\n", mask)', population)
        self.assertIn('"  Mask: %s\\n", mask', parentage)


if __name__ == "__main__":
    unittest.main()
