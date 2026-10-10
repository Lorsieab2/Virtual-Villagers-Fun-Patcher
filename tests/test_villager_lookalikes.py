"""Records that look like villagers and are not (native/shared/villager_lookalike.h).

The games keep some active records in their villager tables that they do not
count as villagers: The Lost Children's Esteemed Elder statues (live,
2026-10-06: the owner's slot 23 held 126 active records, 11 of them statues,
and the game showed Population 115), The Secret City's +0xE94 records, The
Tree of Life's ghosts and New Believers' Reanimate in progress.  An audit the
same day found the Village Population and History logs, the Statistics roster,
the Village Elders and the parentage lookups listing or matching them.  The
rule is compiled here and run on hand-made records; every listing loop is
checked to use it.
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
HEADER = ROOT / "native/shared/villager_lookalike.h"

SOURCE = r'''
#include "villager_lookalike.h"
__declspec(dllexport) int Lookalike(unsigned int stride, const unsigned char *record) {
    return vv_lookalike(stride, record);
}
'''

# stride (each game's record size), marker offset
GAMES = {1: (0x3D8, None), 2: (0xE48C, 0x558), 3: (0x1F8C, 0xE94), 4: (0x2E3C, 0x1CC7), 5: (0x2F44, 0x1CE1)}


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


class TheRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        dll = _build(Path(cls._tmp))
        if dll is None:
            raise unittest.SkipTest("needs the Visual C++ tools")
        cls.dll = ctypes.CDLL(str(dll))
        cls.dll.Lookalike.argtypes = [ctypes.c_uint, ctypes.c_char_p]
        cls.dll.Lookalike.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls) -> None:
        handle = cls.dll._handle
        del cls.dll
        ctypes.windll.kernel32.FreeLibrary(ctypes.c_void_p(handle))
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_each_games_marker(self):
        for game, (stride, marker) in GAMES.items():
            with self.subTest(game=game):
                record = bytearray(stride)
                self.assertEqual(self.dll.Lookalike(stride, bytes(record)), 0, "a villager")
                if marker is None:
                    record[:] = b"\x01" * stride
                    self.assertEqual(self.dll.Lookalike(stride, bytes(record)), 0, "A New Home has none")
                    continue
                record[marker] = 1
                self.assertEqual(self.dll.Lookalike(stride, bytes(record)), 1)


class EveryListUsesIt(unittest.TestCase):
    """Every loop that lists villagers or looks one up skips them (counts per file)."""

    USES = {
        "native/population_export/population_export.c": 3,   # titles, former Heathens, living_villager (History, Population)
        "native/parentage_export/parentage_export.c": 6,     # by id, by name, the tribe, the mother, titles
        "native/statistics_export/statistics_export.c": 1,   # the Village Roster
        "native/statistics_export/village_elders.c": 1,      # the Village Elders
        "native/vvfp_cause_of_death/vvfp_cause_of_death.c": 1,
    }

    def test_the_loops_call_the_rule(self):
        for rel, count in self.USES.items():
            with self.subTest(file=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn('#include "villager_lookalike.h"', text)
                self.assertEqual(text.count("vv_lookalike("), count)


if __name__ == "__main__":
    unittest.main()
