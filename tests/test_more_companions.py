"""The third word of companions (the owner, 2026-11-17: the new multiplier sliders each need a companion of their own,
and the second word VVFP Startup.dll starts was nearly full).

"VVFP More Companions.dll" is the second word's last entry; the patcher ships it, with the first row that ships a
third-word companion, only when a build has one, and writes the third word's bits into "VVFP More Companions.txt"
beside it.  EMULATED: started as VVFP Startup.dll starts it, it reads that number and loads (by its full path in the
patcher's folder) exactly the companions whose bits are set -- none for 0, no file or no number.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

import vv_fun_patcher as patcher

DLL = ROOT / "assets" / "more_companions" / "VVFP More Companions.dll"
CHOICE = "VVFP More Companions.txt"
FAKE_FILE = 0x0000F00D


class Lists(unittest.TestCase):
    def test_the_third_word_is_the_same_in_the_patcher_and_the_companion(self) -> None:
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text("utf-8")
        body = header[header.index("VVFP_STARTUP_COMPANIONS_3[] = {"):header.index("};")]
        self.assertEqual(tuple(re.findall(r'"([^"]+)"', body)), patcher.STARTUP_LOADER_COMPANIONS_3)
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_3[0], "VVFP Meal Scale.dll")
        self.assertLessEqual(len(patcher.STARTUP_LOADER_COMPANIONS_3), 32)
        words = (set(patcher.STARTUP_LOADER_COMPANIONS), set(patcher.STARTUP_LOADER_COMPANIONS_2),
                 set(patcher.STARTUP_LOADER_COMPANIONS_3))
        self.assertEqual(words[0] & words[2], set())
        self.assertEqual(words[1] & words[2], set())

    def test_the_chain_is_the_second_words_entry(self) -> None:
        self.assertEqual(patcher.STARTUP_LOADER_COMPANIONS_2[-1], "VVFP More Companions.dll")
        self.assertLessEqual(len(patcher.STARTUP_LOADER_COMPANIONS_2), 32)

    def test_the_record_pins_the_built_dll(self) -> None:
        record = json.loads((ROOT / "data" / "more_companions_companion.json").read_text("utf-8"))
        self.assertEqual(record["destination"], "VVFP More Companions.dll")
        self.assertEqual(record["source"], "assets/more_companions/VVFP More Companions.dll")
        self.assertEqual(record["sha256"], hashlib.sha256(DLL.read_bytes()).hexdigest().upper())


class Attach(unittest.TestCase):
    def rows(self, *ids: str) -> list:
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        return [public[i] for i in ids]

    def test_shipped_only_with_a_third_word_companion(self) -> None:
        with_meal = patcher._attach_more_companions(self.rows("vv3_hungrier_villagers", "vv3_children_play"))
        names = [c["destination"] for f in with_meal for c in f.raw.get("companion_files", [])]
        self.assertEqual(names.count("VVFP More Companions.dll"), 1)
        self.assertEqual(patcher._startup_loader_mask_3(with_meal), 1)
        self.assertTrue(next(f for f in with_meal if f.id == "vv3_hungrier_villagers").raw["_more_companions_carrier"])
        again = patcher._attach_more_companions(with_meal)
        self.assertEqual([c["destination"] for f in again for c in f.raw.get("companion_files", [])].count(
            "VVFP More Companions.dll"), 1)
        without = patcher._attach_more_companions(self.rows("vv3_children_play"))
        self.assertNotIn("VVFP More Companions.dll",
                         [c["destination"] for f in without for c in f.raw.get("companion_files", [])])
        self.assertEqual(patcher._startup_loader_mask_3(without), 0)

    def test_the_second_word_bit_and_the_choice_file(self) -> None:
        rows = patcher._attach_automatic_companions("vv3", self.rows("vv3_hungrier_villagers"))
        bit = 1 << patcher.STARTUP_LOADER_COMPANIONS_2.index("VVFP More Companions.dll")
        self.assertTrue(patcher._startup_loader_mask_2(rows) & bit)
        with tempfile.TemporaryDirectory() as out:
            patcher._write_more_companions_choice(Path(out), rows)
            found = list(Path(out).rglob(CHOICE))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].read_bytes(), b"1\n")
        rows = patcher._attach_automatic_companions("vv3", self.rows("vv3_children_play"))
        self.assertFalse(patcher._startup_loader_mask_2(rows) & bit)
        with tempfile.TemporaryDirectory() as out:
            patcher._write_more_companions_choice(Path(out), rows)
            self.assertEqual(list(Path(out).rglob(CHOICE)), [])


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class Emulated(unittest.TestCase):
    def setUp(self) -> None:
        if not stock_path(3).is_file():
            self.skipTest("stock executables not present")
        if not DLL.is_file():
            self.skipTest("companion not built")

    def machine(self, setting: bytes | None) -> "Machine":
        m = Machine(render(3, (), "stock"), DLL)
        m.loaded = []

        def open_(p):
            path = p.wstring(p.arg(0))
            ok = setting is not None and path.endswith("\\Virtual Villagers Fun Patcher Files\\" + CHOICE)
            return (FAKE_FILE if ok else 0xFFFFFFFF), 28

        def read(p):
            if p.arg(0) != FAKE_FILE:
                return 0, 20
            data = (setting or b"")[:p.arg(2)]
            p.write(p.arg(1), data)
            p.put32(p.arg(3), len(data))
            return 1, 20

        def load(p):
            m.loaded.append(p.wstring(p.arg(0)))
            return 0, 12                                    # not there: the companion goes on

        m.api_handlers["CreateFileW"] = open_
        m.api_handlers["ReadFile"] = read
        m.api_handlers["CloseHandle"] = lambda p: (1, 4)
        m.api_handlers["LoadLibraryExW"] = load
        return m

    def test_it_loads_exactly_the_named_companions(self) -> None:
        for setting, word, loads in ((b"1\n", 1, ["VVFP Meal Scale.dll"]), (b"0", 0, []), (None, 0, []),
                                     (b"abc", 0, []), (b"", 0, []), (b" 1", 1, ["VVFP Meal Scale.dll"]),
                                     (b"99999999999", 0, []), (b"2", 2, [])):
            with self.subTest(setting=setting):
                m = self.machine(setting)
                m.export("VvfpStartup", 3, 0)
                self.assertEqual(m.export("VvfpMoreCompanionsWord"), word)
                self.assertEqual([path.rsplit("\\", 1)[-1] for path in m.loaded], loads)
                for path in m.loaded:
                    self.assertIn("\\Virtual Villagers Fun Patcher Files\\", path)


if __name__ == "__main__":
    unittest.main()
