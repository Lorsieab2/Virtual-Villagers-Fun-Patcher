"""Equal Division of Labor places villagers by skill progress (v1.35.70), and
A New Home / The Lost Children gain Clear All Skill Preferences.

The owner: "Equal Division of Labor should try and prioritize villagers' skill
progress, otherwise fallback to random equal division" -- "Prioritize skills in
order of most progress."  Each job keeps the same number of seats per sex the
round-robin always gave it; native/shared/equal_division.h hands the seats out
by highest skill first, random for ties and anyone left.
"""
from __future__ import annotations

import re
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/build_equal_division_harness.ps1"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231\bin\Hostx64\x86\cl.exe")
CHECKS = 11
STOCK = ROOT / "research" / "stock-executables"
VV1_C = ROOT / "native/vv1_origins_icons/vv1_origins_icons.c"
VV2_C = ROOT / "native/vv2_origins_icons/vv2_origins_icons.c"


class SeatAssignmentHarness(unittest.TestCase):
    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_harness_passes(self) -> None:
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD)],
                                capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), CHECKS, result.stdout)


class NewHomeWiring(unittest.TestCase):
    def setUp(self) -> None:
        self.c = VV1_C.read_text(encoding="utf-8")
        self.builder = (ROOT / "scripts/build_vv1_origins_feature.py").read_text(encoding="utf-8")

    def test_the_result_export_receives_the_array_and_reseats_by_skill(self) -> None:
        self.assertIn("ShowOriginsEqualDivisionResult=_ShowOriginsEqualDivisionResult@24",
                      (ROOT / "native/vv1_origins_icons/vv1_origins_icons.def").read_text(encoding="utf-8"))
        self.assertIn("push dword ptr [edi + 0xADE8]\n            push 0x{EQUAL_DIVISION_FEMALE_COUNTS_VA:X}",
                      self.builder)
        self.assertIn("vv1_equal_division_by_skill(records, include_parenting, male_counts, female_counts);",
                      self.c)
        # Same code table the core writes, and the skill each code rates.
        self.assertIn("static const int vv1_ed_code[5] = { 1, 4, 3, 5, 2 };", self.c)
        self.assertIn("static const int vv1_ed_skill[5] = { 0x3C4, 0x3C0, 0x3CC, 0x3C8, 0x3BC };", self.c)
        self.assertIn("EQUAL_DIVISION_TABLE_BYTES = bytes([1, 4, 3, 5, 2])", self.builder)

    def test_a_mismatched_array_keeps_the_round_robin(self) -> None:
        body = self.c.split("static void vv1_equal_division_by_skill(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("if (seated != count) {", body)
        self.assertIn("VV_IS_GOLDEN_CHILD(rec)", body)

    @unittest.skipUnless((STOCK / "Virtual Villagers - A New Home.exe").is_file(), "stock A New Home absent")
    def test_the_code_to_skill_table_is_the_stock_choosers(self) -> None:
        import pefile
        exe = STOCK / "Virtual Villagers - A New Home.exe"
        pe = pefile.PE(str(exe), fast_load=True)
        data = exe.read_bytes()
        table = pe.get_offset_from_rva(0x439CAC - 0x400000)
        skill_of = {}
        for code in range(1, 6):
            case = struct.unpack_from("<I", data, table + 4 * (code - 1))[0]
            at = pe.get_offset_from_rva(case - 0x400000)
            self.assertEqual(data[at:at + 2], bytes.fromhex("8BB7"))
            skill_of[code] = struct.unpack_from("<I", data, at + 2)[0]
        codes = (1, 4, 3, 5, 2)
        skills = (0x3C4, 0x3C0, 0x3CC, 0x3C8, 0x3BC)
        self.assertEqual({c: skill_of[c] for c in codes}, dict(zip(codes, skills)))


class LostChildrenWiring(unittest.TestCase):
    def setUp(self) -> None:
        self.c = VV2_C.read_text(encoding="utf-8")

    def test_the_codes_are_the_games_own(self) -> None:
        # Farming, Building, Research, Healing, Breeding.
        self.assertIn("static const int vv2_ed_code[5] = { 1, 5, 4, 3, 2 };", self.c)
        self.assertIn("static const int vv2_ed_skill[5] = { 0x7EC, 0x7E8, 0x7F4, 0x7F0, 0x7E4 };", self.c)
        self.assertNotIn("= seat + 1;   /* 1..5 */", self.c)

    def test_the_seat_counts_are_the_old_round_robin(self) -> None:
        self.assertIn("vved_cycle_quota(male_total, professions, 0, quota);", self.c)
        self.assertIn("vved_cycle_quota(female_total, professions, male_total % professions,", self.c)

    @unittest.skipUnless((STOCK / "Virtual Villagers - The Lost Children.exe").is_file(),
                         "stock The Lost Children absent")
    def test_the_code_to_skill_table_is_the_stock_choosers(self) -> None:
        import pefile
        exe = STOCK / "Virtual Villagers - The Lost Children.exe"
        pe = pefile.PE(str(exe), fast_load=True)
        data = exe.read_bytes()
        at = pe.get_offset_from_rva(0x449DD2 - 0x400000)
        self.assertEqual(data[at:at + 6], bytes.fromhex("8B87F8070000"), "mov eax, [edi+0x7F8]")
        table = pe.get_offset_from_rva(0x449E60 - 0x400000)
        skill_of = {}
        for code in range(1, 6):
            case = struct.unpack_from("<I", data, table + 4 * (code - 1))[0]
            c_at = pe.get_offset_from_rva(case - 0x400000)
            self.assertEqual(data[c_at:c_at + 2], bytes.fromhex("8BB7"))
            skill_of[code] = struct.unpack_from("<I", data, c_at + 2)[0]
        self.assertEqual(skill_of, {1: 0x7EC, 2: 0x7E4, 3: 0x7F0, 4: 0x7F4, 5: 0x7E8})


class ClearAllSkillPreferences(unittest.TestCase):
    def setUp(self) -> None:
        self.c = VV1_C.read_text(encoding="utf-8")
        self.vv2 = VV2_C.read_text(encoding="utf-8")

    def test_half_the_equal_division_price_and_free_when_free(self) -> None:
        self.assertIn("#define VV_CLEAR_PREFS_COST 500000", self.c)
        self.assertIn("int price = vvfp_story_price(VV_STORY_GAME, VV_CLEAR_PREFS_COST);", self.c)

    def test_it_clears_to_the_games_none_and_charges_only_on_a_change(self) -> None:
        body = self.c.split("static int vv_clear_prefs_purchase(HWND owner) {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("pref_offset = 0x3D0;", body)
        self.assertIn("pref_offset = 0x7F8;", body)
        self.assertIn("*(int *)(rec + pref_offset) = 0;", body)
        self.assertLess(body.index("if (changed == 0) {"), body.index("*(int *)(world + tech_offset) -= price;"))
        self.assertIn("is already cleared. ", body)

    def test_both_dialogs_carry_the_row(self) -> None:
        rc1 = (ROOT / "native/vv1_origins_icons/vv1_origins_icons.rc").read_text(encoding="utf-8")
        rc2 = (ROOT / "native/vv2_origins_icons/vv2_origins_icons.rc").read_text(encoding="utf-8")
        for rc, button in ((rc1, 1012), (rc2, 1014)):
            self.assertIn('"Clear All Skill Preferences"', rc)
            self.assertIn('"500,000 tech points"', rc)
            self.assertIn(f'PUSHBUTTON  "Buy", {button},', rc)
        self.assertIn("if (command == VV1_CLEAR_PREFS_ID) {", self.c)
        self.assertIn("if (command == ID_VV2_CLEAR_PREFS) {", self.vv2)


if __name__ == "__main__":
    unittest.main()
