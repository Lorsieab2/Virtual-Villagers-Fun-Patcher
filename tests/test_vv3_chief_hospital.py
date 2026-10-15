"""Static checks for "Tribal Chief Supervises the Hospital" (The Secret City).

The row, its companion and the guide are checked from the files; the stock
bytes are checked against the stock executable when it is in the checkout.
The live effect is NOT verified here: it needs the owner's own play test.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ID = "vv3_chief_hospital_supervision"
DLL_LEAF = "VVFP VV3 Chief Hospital.dll"
DLL = ROOT / "assets" / "chief_hospital" / DLL_LEAF
ROW = ROOT / "data" / "vv3_chief_hospital_feature.json"
STOCK_EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
SITE = 0x45739A
STOCK = bytes.fromhex("84C00F848F000000")


def load_row() -> dict:
    return json.loads(ROW.read_text(encoding="utf-8"))


class ChiefHospitalRow(unittest.TestCase):

    def test_the_row_is_present_for_vv3_and_enabled(self):
        row = load_row()
        self.assertEqual(row["id"], ID)
        self.assertEqual(row["game_id"], "vv3")
        self.assertTrue(row["enabled"])
        self.assertTrue(row["catalog_enabled"])
        self.assertFalse(row["catalog_hidden"])

    def test_default_on_for_vv3_only(self):
        # Every fun patch starts selected (vv_fun_patcher_gui.py), so the row
        # is default on exactly when the loader lists it for VV3 and no other game.
        import vv_fun_patcher as vfp
        self.assertEqual([p.name for p in vfp.CHIEF_HOSPITAL_FEATURE_PATHS], [ROW.name])
        games = {p.game_id for p in vfp.load_fun_patches() if p.id == ID}
        self.assertEqual(games, {"vv3"})

    def test_no_other_row_is_needed_and_no_bytes_are_patched(self):
        row = load_row()
        self.assertEqual(row["dependencies"], [])
        self.assertEqual(row["patches"], [])

    def test_the_declared_detour_is_the_stock_test_and_je(self):
        detours = load_row()["runtime_detours"]
        self.assertEqual(len(detours), 1)
        self.assertEqual(int(detours[0]["va"], 16), SITE)
        self.assertEqual(bytes.fromhex(detours[0]["stock_bytes"]), STOCK)
        self.assertEqual(STOCK, bytes([0x84, 0xC0]) + bytes([0x0F, 0x84]) + (0x457431 - (SITE + 8)).to_bytes(4, "little"))

    @unittest.skipUnless(STOCK_EXE.is_file(), "the stock executables are not in this checkout")
    def test_the_stock_executable_has_those_bytes_at_the_site(self):
        import pefile
        pe = pefile.PE(str(STOCK_EXE), fast_load=True)
        data = pe.get_memory_mapped_image()
        rva = SITE - pe.OPTIONAL_HEADER.ImageBase
        self.assertEqual(data[rva:rva + 8], STOCK)

    def test_the_companion_is_shipped_and_hash_pinned(self):
        row = load_row()
        [item] = row["companion_files"]
        self.assertEqual(item["destination"], DLL_LEAF)
        self.assertEqual(item["source"], f"assets/chief_hospital/{DLL_LEAF}")
        self.assertTrue(DLL.is_file())
        self.assertEqual(hashlib.sha256(DLL.read_bytes()).hexdigest().upper(), item["sha256"])

    def test_the_loader_knows_the_companion_as_its_last_entry(self):
        import vv_fun_patcher as vfp
        self.assertEqual(vfp.STARTUP_LOADER_COMPANIONS[-1], DLL_LEAF)
        header = (ROOT / "native" / "shared" / "startup_companions.h").read_text(encoding="utf-8")
        body = header[header.index("VVFP_STARTUP_COMPANIONS[] = {"):]
        body = body[:body.index("};")]
        self.assertEqual(re.findall(r'"([^"]+)"', body)[-1], DLL_LEAF)
        self.assertLess(len(vfp.STARTUP_LOADER_COMPANIONS), 30)

    def test_the_dll_exports_only_vvfpstartup_and_contains_the_stub_constants(self):
        import pefile
        pe = pefile.PE(str(DLL))
        names = {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.assertIn(b"VvfpStartup", names)
        self.assertEqual({n for n in names if n.startswith(b"Vvfp")}, {b"VvfpStartup"})
        data = DLL.read_bytes()
        self.assertIn(bytes.fromhex("6831744500"), data)      # push 0x457431 (the stock failure)
        self.assertIn(bytes.fromhex("68A2734500"), data)      # push 0x4573A2 (the cure goes on)
        self.assertIn(bytes.fromhex("B860FC4500"), data)      # mov eax, 0x45FC60 (the chief's roll)
        self.assertIn(bytes.fromhex("6A09"), data)            # push 9 (the hospital's Healing site)

    def test_the_companion_only_installs_for_the_secret_city(self):
        source = (ROOT / "native" / "vvfp_chief_hospital" / "vvfp_chief_hospital.c").read_text(encoding="utf-8")
        self.assertIn("#define VV3_GAME 3", source)
        self.assertIn("game != VV3_GAME", source)


class ChiefHospitalGuide(unittest.TestCase):

    def test_the_guide_has_an_entry_for_the_row(self):
        guide = json.loads((ROOT / "data" / "how_to_use.json").read_text(encoding="utf-8"))
        entries = [e for e in self._entries(guide) if ID in e.get("ids", [])]
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]["guide"])
        self.assertTrue(any("not yet tested" in line.lower() for line in entries[0]["guide"]))

    def test_the_readme_names_the_patch(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"`{ID}`", readme)
        self.assertIn("**Tribal Chief Supervises the Hospital**", readme)

    @staticmethod
    def _entries(node):
        if isinstance(node, dict):
            yield node
            for value in node.values():
                yield from ChiefHospitalGuide._entries(value)
        elif isinstance(node, list):
            for value in node:
                yield from ChiefHospitalGuide._entries(value)


if __name__ == "__main__":
    unittest.main()
