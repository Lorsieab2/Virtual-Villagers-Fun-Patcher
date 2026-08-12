import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import get_fun_patch, load_fun_patches  # noqa: E402


class VV2RequiredFixTests(unittest.TestCase):
    def test_only_current_vv2_origins_menu_routes_are_catalog_selectable(self) -> None:
        ids = {patch.id for patch in load_fun_patches()}
        self.assertNotIn("vv2_full_mastery_all_stage_a_candidate", ids)
        self.assertNotIn("vv2_individual_full_mastery_candidate", ids)
        self.assertIn("vv2_enable_origins_exclusive_features", ids)
        self.assertIn("vv2_origins_village_wide_upgrades", ids)

    def test_vv2_record_layout_and_mastery_abi_are_bound(self) -> None:
        feature = get_fun_patch("vv2_origins_village_wide_upgrades")
        fields = feature.raw["record_fields"]
        self.assertEqual(fields["like_slot_count"], 62)
        self.assertEqual(fields["dislike_slot_count"], 62)
        self.assertEqual(fields["likes_offset"], "0x5F0")
        self.assertEqual(fields["dislikes_offset"], "0x6E8")
        self.assertEqual(fields["totem_offset"], "0x558")
        self.assertEqual(fields["native_skill_writer"], "0x445430")
        self.assertEqual(fields["native_mastery_manager"], "0x44F4E0")
        self.assertNotIn("native_mastery_evaluator", fields)

    def test_vv2_detail_menu_uses_exact_mastery_and_all_62_preference_slots(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        detail_menu = source.split("detail_menu,", 1)[1].split(
            "tech_increment,", 1
        )[0]
        self.assertEqual(detail_menu.count("mov ecx, 62"), 2)
        for offset in ("0x7E4", "0x7E8", "0x7EC", "0x7F0", "0x7F4"):
            self.assertIn(f"cmp dword ptr [edx + {offset}], 100", detail_menu)
        self.assertNotIn(", 90", detail_menu)
        self.assertIn("for value in (2, 5, 1, 3, 4)", source)
        self.assertNotIn("call 0x44D4C0", source)

    def test_vv2_running_only_inserts_before_clearing_dislikes(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        detail_running = source.split("detail_running:", 1)[1].split(
            "detail_success:", 1
        )[0]
        self.assertIn("test ebp, 1\n            jnz detail_success", detail_running)
        self.assertIn("test edi, edi\n            jz detail_success", detail_running)
        self.assertLess(
            detail_running.index("mov dword ptr [edi]"),
            detail_running.index("running_remove_dislikes:"),
        )
        village = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("leaves already-Running or full-like villagers unchanged", village)
        self.assertIn("running_existing:\n                inc ebp\n                jmp running_next", village)

    def test_vv2_cure_all_restores_partial_health_and_clears_sickness(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        cure = source.split("cure_all:", 1)[1].split("cure_done:", 1)[0]
        self.assertIn("cmp dword ptr [edx + 0x52C], 80", cure)
        self.assertIn("mov dword ptr [edx + 0x52C], 100", cure)
        self.assertIn("mov dword ptr [edx + 0x53C], 0", cure)

    def test_vv2_tech_dialog_marks_rows_six_to_eight_as_buyable(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("or dword ptr [esp + 0x10], 0xA01C0", source)
        native = (ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("STATE_VILLAGE_WIDE_BUY = 0x80000", native)
        self.assertIn('SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy")', native)

    def test_vv2_uses_a_dedicated_companion_and_release_excludes_duplicates(self) -> None:
        feature = get_fun_patch("vv2_enable_origins_exclusive_features")
        companion = feature.raw["companion_files"][0]
        self.assertEqual(companion["destination"], "VVFP VV2 Origins Icons.dll")
        path = ROOT / companion["source"]
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(), companion["sha256"]
        )
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/origins/VVFP VV2 Origins Icons.dll"', release)
        for old in (
            "data/candidates/vv2_full_mastery_all_candidate.json",
            "data/candidates/vv2_individual_full_mastery_candidate.json",
            "VVFP VV2 Full Mastery Candidate.dll",
        ):
            self.assertNotIn(old, release)


if __name__ == "__main__":
    unittest.main()
