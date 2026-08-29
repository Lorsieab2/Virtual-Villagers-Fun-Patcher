"""Locks the VV3 Equal Division of Labor Tech-screen upgrades (buttons 1011/1012).

The feature sets each eligible villager's job-preference checkmark (record +0xEC0,
an index: 0=Farming 1=Parenting 2=Healing 3=Research 4=Building) round-robin in the
order Farmer, Builder, Researcher, Healer[, Parenting] = indices [0,4,3,2(,1)], with
males and females on independent counters, skipping the Tribal Chief (+0xE80 != 0).
Wording follows OFFICIAL Origins Upgrade Prompts.xlsx (Tech rows 11-12, 1,000,000 each).
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLL_C = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
DLL_DEF = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.def"
DLL_RC = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.rc"
BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"


class VV3EqualDivisionOfLaborTests(unittest.TestCase):
    def setUp(self) -> None:
        self.c = DLL_C.read_text(encoding="utf-8")
        self.deff = DLL_DEF.read_text(encoding="utf-8")
        self.rc = DLL_RC.read_text(encoding="utf-8")
        self.builder = BUILDER.read_text(encoding="utf-8")

    def test_dll_exports_the_worker(self) -> None:
        self.assertIn("EqualDivisionOfLabor=_EqualDivisionOfLabor@4", self.deff)
        self.assertIn(
            "int __stdcall EqualDivisionOfLabor(int includeParenting)", self.c
        )

    def test_dll_uses_the_confirmed_field_offsets_and_cycle(self) -> None:
        # preferred-skill index, gender, chief flag, and the tech-point pool.
        self.assertIn("#define VV3_PREF       0xEC0", self.c)
        self.assertIn("#define VV3_GENDER     0xDC8", self.c)
        self.assertIn("#define VV3_CHIEF      0xE80", self.c)
        self.assertIn("#define VV3_TECH_POINTS 0x00582644u", self.c)
        self.assertIn("#define EDL_COST       1000000", self.c)
        # Farmer, Builder, Researcher, Healer, Parenting -> +0xEC0 index values.
        self.assertIn("static const int cycle[5] = {0, 4, 3, 2, 1};", self.c)
        # No Parenting drops the last cycle entry (length 4).
        self.assertIn("int cyclen = includeParenting ? 5 : 4;", self.c)
        # Males and females advance on independent counters.
        self.assertIn("male_ctr", self.c)
        self.assertIn("female_ctr", self.c)

    def test_dll_eligibility_is_everyone_but_the_chief(self) -> None:
        worker = self.c.split("EqualDivisionOfLabor(int includeParenting)", 1)[1]
        # active villagers only, and the Chief (+0xE80 != 0) is skipped/counted.
        self.assertIn("if (rec[VV3_ACTIVE] == 0) continue;", worker)
        self.assertIn("if (rec[VV3_CHIEF] != 0) { skipped++; continue; }", worker)
        # no age gate (children of any age are eligible).
        self.assertNotIn("VV3_AGE", worker)

    def test_dll_wording_matches_official_sheet(self) -> None:
        self.assertIn("Set %u %s' Job Preferences.", self.c)
        self.assertIn("%s: %u %s (%u Male, %u Female).", self.c)
        self.assertIn("Skipped %u %s: is Tribal Chief.", self.c)  # VV3, not Golden Child
        self.assertNotIn("Golden Child", self.c)
        self.assertIn(
            "No villagers were eligible. No tech points have been deducted.", self.c
        )
        self.assertIn("Not enough tech points.", self.c)
        # profession labels print in the sheet's order Farming/Building/Research/Healing/Breeding.
        self.assertIn(
            '{"Farming", "Building", "Research", "Healing", "Breeding"}', self.c
        )
        # confirm names are the full sheet titles (the dialog builds "Do you want to buy <name>...").
        self.assertIn(
            '"Equal Division of Labor (Includes Parenting)"', self.c
        )
        self.assertIn('"Equal Division of Labor (No Parenting)"', self.c)

    def test_dialog_has_both_buy_rows(self) -> None:
        self.assertIn('PUSHBUTTON  "Buy", 1011', self.rc)
        self.assertIn('PUSHBUTTON  "Buy", 1012', self.rc)
        self.assertIn("ID_BUY_LAST = 1013", self.c)

    def test_payload_routes_the_two_buttons_to_the_dll(self) -> None:
        # dispatch: buttons 11/12 branch to the handlers.
        self.assertIn("cmp ebx, 11\n            je do_equal_division_incl", self.builder)
        self.assertIn("cmp ebx, 12\n            je do_equal_division_no", self.builder)
        # includeParenting = 1 (row 11) / 0 (row 12), then call the DLL export.
        self.assertIn("do_equal_division_incl:\n            push 1", self.builder)
        self.assertIn("do_equal_division_no:\n            push 0", self.builder)
        self.assertIn("edl_export", self.builder)
        self.assertIn('("edl_export", "EqualDivisionOfLabor")', self.builder)


if __name__ == "__main__":
    unittest.main()
