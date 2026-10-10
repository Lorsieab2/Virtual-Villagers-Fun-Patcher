"""The Village Population and History logs list the living, never a body awaiting burial.

Live, 2026-10-10 (The Lost Children, release candidate 6fbad819): a seven-villager tribe
starved; after a clean quit the Population log and the new History block listed all seven
unburied skeletons as living villagers with ages.  The save held all seven at health 0.  An
occupied record at health 0 or below is a body: neither living (these logs) nor yet dead (its
Death record comes from the burial, the Cause of Death companion).

The exporter's own predicate (living_villager in native/population_export/population_export.c)
is compiled here and run on hand-made records of every game; the runtime harness
(population_export_harness.c) checks the same through the shipped DLL.
"""
from __future__ import annotations

import ctypes
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/population_export/population_export.c"
COD = ROOT / "native/vvfp_cause_of_death/vvfp_cause_of_death.c"

SOURCE = r'''
#include "population_export.c"
__declspec(dllexport) int Living(int game, const unsigned char *record) {
    return living_villager(&GAME_LAYOUTS[game], record);
}
__declspec(dllexport) int Sane(int game) { return layout_is_sane(&GAME_LAYOUTS[game]); }
__declspec(dllexport) unsigned int Field(int game, int which) {
    const struct game_layout *g = &GAME_LAYOUTS[game];
    return which == 0 ? g->active : which == 1 ? g->health : g->stride;
}
'''

# The Cause of Death companion's health column (its living test is rec_health > 0).
HEALTH = {1: 0x344, 2: 0x52C, 3: 0xE78, 4: 0x1C40, 5: 0x1C40}
STATUE = 0x558          # The Lost Children's Esteemed Elder statue (villager_lookalike.h)
REANIMATING = 0x1CE1    # New Believers: the villager being reanimated


def _build(folder: Path) -> Path | None:
    name = "vcvars32.bat" if struct.calcsize("P") == 4 else "vcvars64.bat"
    vcvars = None
    for base in (r"C:\Program Files\Microsoft Visual Studio", r"C:\Program Files (x86)\Microsoft Visual Studio"):
        for candidate in sorted(Path(base).glob(f"*/*/VC/Auxiliary/Build/{name}")):
            vcvars = candidate
    if vcvars is None:
        return None
    (folder / "t.c").write_text(SOURCE, encoding="utf-8")
    shared = ROOT / "native/shared"
    command = (f'call "{vcvars}" >nul && cl /nologo /LD /O2 /I "{shared}" /I "{EXPORTER.parent}" t.c '
               f'"{shared / "village_identity.c"}" "{shared / "save_folder.c"}" '
               f'/Fe:t.dll /link /NOLOGO kernel32.lib shell32.lib >nul')
    result = subprocess.run(command, shell=True, cwd=folder, capture_output=True, text=True)
    return folder / "t.dll" if result.returncode == 0 and (folder / "t.dll").is_file() else None


class TheLivingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp()
        dll = _build(Path(cls._tmp))
        if dll is None:
            shutil.rmtree(cls._tmp, ignore_errors=True)
            raise unittest.SkipTest("needs the Visual C++ tools")
        cls.dll = ctypes.CDLL(str(dll))
        cls.dll.Living.argtypes = [ctypes.c_int, ctypes.c_char_p]
        cls.dll.Living.restype = ctypes.c_int
        cls.dll.Sane.argtypes = [ctypes.c_int]
        cls.dll.Sane.restype = ctypes.c_int
        cls.dll.Field.argtypes = [ctypes.c_int, ctypes.c_int]
        cls.dll.Field.restype = ctypes.c_uint

    @classmethod
    def tearDownClass(cls) -> None:
        handle = cls.dll._handle
        del cls.dll
        ctypes.windll.kernel32.FreeLibrary(ctypes.c_void_p(handle))
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _record(self, game: int, active: int, health: int) -> bytearray:
        record = bytearray(self.dll.Field(game, 2))
        record[self.dll.Field(game, 0)] = active
        struct.pack_into("<i", record, self.dll.Field(game, 1), health)
        return record

    def test_health_is_the_cause_of_death_companions(self):
        for game, offset in HEALTH.items():
            with self.subTest(game=game):
                self.assertEqual(self.dll.Field(game, 1), offset)
                self.assertTrue(self.dll.Sane(game))

    def test_a_body_is_not_living(self):
        for game in HEALTH:
            with self.subTest(game=game):
                self.assertTrue(self.dll.Living(game, bytes(self._record(game, 1, 100))))
                self.assertTrue(self.dll.Living(game, bytes(self._record(game, 1, 1))))
                self.assertFalse(self.dll.Living(game, bytes(self._record(game, 1, 0))), "a skeleton")
                self.assertFalse(self.dll.Living(game, bytes(self._record(game, 1, -5))), "below 0")
                self.assertFalse(self.dll.Living(game, bytes(self._record(game, 0, 100))), "an empty slot")

    def test_a_statue_is_still_not_a_villager(self):
        record = self._record(2, 1, 100)
        record[STATUE] = 1
        self.assertFalse(self.dll.Living(2, bytes(record)))

    def test_new_believers_villager_being_reanimated_stays_a_lookalike(self):
        """Excluded as before, as the game's own list and the Statistics roster exclude it."""
        for health in (0, 100):
            with self.subTest(health=health):
                record = self._record(5, 1, health)
                record[REANIMATING] = 1
                self.assertFalse(self.dll.Living(5, bytes(record)))


class TheLoopsUseIt(unittest.TestCase):
    def test_population_and_history_skip_bodies(self):
        text = EXPORTER.read_text(encoding="utf-8")
        for name in ("append_history(", "WriteVillagePopulation("):
            with self.subTest(loop=name):
                body = text[text.index(name):]
                body = body[:body.index("\n}\n")]
                self.assertIn("if (!living_villager(g, record)) {", body)

    def test_the_cause_of_death_table_agrees(self):
        text = COD.read_text(encoding="utf-8")
        rows = re.findall(r"\{ 0x[0-9A-F]+u, [01], (?:0x[0-9A-F]+|\d+)u, 0x[0-9A-F]+u, \d+u, 0x[0-9A-F]+u, (0x[0-9A-F]+)u,", text)
        self.assertEqual([int(v, 16) for v in rows], [HEALTH[g] for g in sorted(HEALTH)])


class TheCheckerComparesTheLiving(unittest.TestCase):
    """scripts/vvfp_consistency_check.py compares the Population and History logs with the
    save's villagers less its bodies, so an unburied body is no "only in the save" note."""

    def test_living_only_drops_bodies(self):
        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location("vvfp_consistency_check_bodies",
                                                      ROOT / "scripts" / "vvfp_consistency_check.py")
        checker = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = checker
        spec.loader.exec_module(checker)
        alive = checker.Villager(rank=0, name="Kiwi", male=True, age=200, head=1, body=1, skills=[], health=80)
        body = checker.Villager(rank=1, name="Bones", male=True, age=900, head=2, body=2, skills=[], health=0)
        below = checker.Villager(rank=2, name="Dust", male=False, age=900, head=2, body=2, skills=[], health=-1)
        self.assertEqual([v.name for v in checker.living_only([alive, body, below])], ["Kiwi"])
        self.assertEqual(checker.HEALTH, {2: -0x38, 3: 0xA4, 4: 0xA4, 5: 0xA4})


if __name__ == "__main__":
    unittest.main()
