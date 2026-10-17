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
INDEX_BYTE = 0x458D94
DIRECTING = {
    0x44B637: bytes.fromhex("FF248D88BB4400"),       # the Directing-work handler's site jump
    0x45A753: bytes.fromhex("506A028D8EAC0E0000"),   # the Medicine practice gain
    INDEX_BYTE: b"\x00",                             # site 9's index in the chief's site switch
}
STUDY_STEP_RETURN = 0x46206B


def load_row() -> dict:
    return json.loads(ROW.read_text(encoding="utf-8"))


def stock_image() -> tuple[bytes, int]:
    import pefile
    pe = pefile.PE(str(STOCK_EXE), fast_load=True)
    return pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase


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
        self.assertEqual(int(detours[0]["va"], 16), SITE)
        self.assertEqual(bytes.fromhex(detours[0]["stock_bytes"]), STOCK)
        self.assertEqual(STOCK, bytes([0x84, 0xC0]) + bytes([0x0F, 0x84]) + (0x457431 - (SITE + 8)).to_bytes(4, "little"))

    def test_the_directing_work_places_are_declared(self):
        detours = {int(d["va"], 16): d for d in load_row()["runtime_detours"]}
        self.assertEqual(set(detours), {SITE} | set(DIRECTING))
        for va, stock in DIRECTING.items():
            with self.subTest(va=hex(va)):
                self.assertEqual(bytes.fromhex(detours[va]["stock_bytes"]), stock)
                self.assertEqual(len(detours[va]["written_bytes"]) // 2, len(stock))
        self.assertEqual(detours[INDEX_BYTE]["written_bytes"], "0B")

    @unittest.skipUnless(STOCK_EXE.is_file(), "the stock executables are not in this checkout")
    def test_the_stock_executable_has_those_bytes_at_the_site(self):
        data, base = stock_image()
        rva = SITE - base
        self.assertEqual(data[rva:rva + 8], STOCK)
        for va, stock in DIRECTING.items():
            with self.subTest(va=hex(va)):
                self.assertEqual(data[va - base:va - base + len(stock)], stock)


@unittest.skipUnless(STOCK_EXE.is_file(), "the stock executables are not in this checkout")
class ChiefHospitalChainInTheStockExecutable(unittest.TestCase):
    """The proven chain, re-read from the stock executable: the action ids,
    the say strings, the stand position and the study's skill gain."""

    @classmethod
    def setUpClass(cls):
        cls.data, cls.base = stock_image()

    def at(self, va, length):
        return self.data[va - self.base:va - self.base + length]

    def dword(self, va):
        return int.from_bytes(self.at(va, 4), "little")

    def say(self, string_id):
        # The game's own string fill (0x42F4F0) indexes 16-byte records
        # {id, enum, display, override} from 0x4AB990.
        self.assertEqual(self.at(0x42F510, 5), bytes.fromhex("B990B94A00"))
        for k in range(0x4BA):
            rec = 0x4AB990 + 16 * k
            if self.dword(rec) == string_id:
                return self.cstr(self.dword(rec + 4)), self.cstr(self.dword(rec + 8))
        return None

    def cstr(self, va):
        raw = self.data[va - self.base:]
        return raw[:raw.index(b"\0")].decode("latin1")

    def registered(self, action, handler):
        # push handler / push action / call 0x4411B0 (the action table)
        push_action = (b"\x6A" + bytes([action])) if action < 0x80 else (b"\x68" + action.to_bytes(4, "little"))
        return (b"\x68" + handler.to_bytes(4, "little") + push_action) in self.data

    def test_directing_work_is_action_0x81_and_says_eSayDirectWork(self):
        self.assertEqual(self.say(0x219), ("eSayDirectWork", "Directing work"))
        self.assertTrue(self.registered(0x81, 0x44B5F0))
        self.assertEqual(self.at(0x44B5F9, 5), bytes.fromhex("6819020000"))   # push 0x219
        # 0x21A, which the research notes once took for it, is "Refusing".
        self.assertEqual(self.say(0x21A), ("eSayRefusing", "Refusing"))

    def test_concerned_about_the_sick_is_action_0x8a_and_its_stand_area(self):
        self.assertEqual(self.say(0x1E4), ("eSayConcernedSick", "Concerned about the sick"))
        self.assertTrue(self.registered(0x8A, 0x452540))
        self.assertEqual(self.at(0x452548, 5), bytes.fromhex("68E4010000"))   # push 0x1E4
        self.assertEqual(self.at(0x452570, 2), bytes.fromhex("6A32"))         # rand(0x32)
        self.assertEqual(self.at(0x452579, 5), bytes.fromhex("6896000000"))   # rand(0x96)
        self.assertEqual(self.at(0x45257E, 6), bytes.fromhex("81C665060000")) # + 0x665
        self.assertEqual(self.at(0x452590, 5), bytes.fromhex("057B040000"))   # + 0x47B
        # The chief's chooser picks it (push 0x8A at 0x45BDED).
        self.assertEqual(self.at(0x45BDED, 5), bytes.fromhex("688A000000"))

    def test_the_bases_keep_every_step_inside_the_concerned_area(self):
        # The handler walks to base + rand(0x1E); the stub's bases are
        # 0x47B + rand(0x79) and 0x665 + rand(0x15).
        self.assertEqual(self.at(0x44B8B8, 2), bytes.fromhex("6A1E"))
        self.assertLessEqual(0x47B + 0x78 + 0x1D, 0x47B + 0x96 - 1)
        self.assertLessEqual(0x665 + 0x14 + 0x1D, 0x665 + 0x32 - 1)

    def test_stock_site_9_is_cleared_and_given_nothing(self):
        # 0x458C70: index = byte [site - 9 + 0x458D94]; site 9 -> entry 0 ->
        # 0x458D0B (clears +0xEA0); entry 11 is the Directing-work order.
        self.assertEqual(self.at(0x458C7B, 3), bytes.fromhex("83C0F7"))       # add eax, -9
        self.assertEqual(self.at(0x458D94, 1), b"\x00")
        self.assertEqual(self.dword(0x458D64), 0x458D0B)
        self.assertEqual(self.dword(0x458D64 + 4 * 11), 0x458D4C)
        self.assertEqual(self.at(0x458D0B, 10), bytes.fromhex("C787A00E000000000000"))
        self.assertEqual(self.at(0x458D51, 5), bytes.fromhex("6881000000"))   # push 0x81
        # and the Directing-work handler has no place for site 9 (exit 0x44BB80)
        self.assertEqual(self.dword(0x44BB88 + 4 * self.at(0x44BBBC + 5, 1)[0]), 0x44BB80)

    def test_the_chief_is_given_no_action_by_the_hospital_drop(self):
        self.assertEqual(self.at(0x4215F6, 10), bytes.fromhex("C786A00E000009000000"))  # site 9
        self.assertEqual(self.at(0x421600, 10), bytes.fromhex("8A86800E000084C0753C"))  # chief -> return
        self.assertEqual(self.at(0x421620, 5), bytes.fromhex("68BD000000"))             # others: 0xBD

    def test_studying_medicine_ends_with_a_medicine_practice_roll(self):
        self.assertEqual(self.say(0x472), ("eStudyingMedicine", "Studying medicine"))
        self.assertTrue(self.registered(0xBD, 0x451890))
        self.assertEqual(self.at(0x4519FC, 9), bytes.fromhex("6A028BCEE88BF80000"))     # op 7, skill 2
        self.assertEqual(self.at(0x4612B7, 8), bytes.fromhex("C744243807000000"))       # op 7
        self.assertEqual(self.at(0x462066, 5), bytes.fromhex("E85582FFFF"))             # 0x45A2C0
        self.assertEqual(STUDY_STEP_RETURN, 0x462066 + 5)
        self.assertEqual(self.at(0x45A75C, 5), bytes.fromhex("E8DFAFFFFF"))             # 0x455740

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
        self.assertIn(bytes.fromhex("83F8057407FF248D88BB4400"), data)  # site 9, else the stock jump
        self.assertIn(bytes.fromhex("057B040000"), data)      # + 0x47B (the Concerned-about-the-sick area)
        self.assertIn(bytes.fromhex("0565060000"), data)      # + 0x665
        self.assertIn(bytes.fromhex("686BB84400C3"), data)    # on to the handler's plain pose 0x44B86B
        self.assertIn(bytes.fromhex("506A028D8EAC0E0000685CA74500C3"), data)  # the stolen gain, then 0x45A75C
        self.assertIn(bytes.fromhex("6B204600"), data)        # 0x46206B, the study step's return
        self.assertIn(bytes.fromhex("B830EF4500"), data)      # 0x45EF30, the game's chief lookup

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
