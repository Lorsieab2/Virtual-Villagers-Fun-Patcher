import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import get_fun_patch, load_fun_patches  # noqa: E402


class VV3RequiredFixTests(unittest.TestCase):
    def test_only_the_current_vv3_origins_menu_routes_are_selectable(self) -> None:
        ids = {patch.id for patch in load_fun_patches()}
        self.assertIn("vv3_origins_village_wide_upgrades", ids)
        self.assertIn("vv3_enable_origins_exclusive_features", ids)
        for old in (
            "vv3_full_mastery_all_stage_a_candidate",
            "vv3_individual_full_mastery_candidate",
            "vv3_individual_grant_running_candidate",
            "vv3_full_heal_cure_all_candidate",
        ):
            self.assertNotIn(old, ids)

    def test_vv3_record_layout_and_native_mastery_abi_are_bound(self) -> None:
        feature = get_fun_patch("vv3_origins_village_wide_upgrades")
        fields = feature.raw["record_fields"]
        self.assertEqual(fields["stride"], "0x1F8C")
        self.assertEqual(fields["active_offset"], "0xF10")
        self.assertEqual(fields["health_offset"], "0xE78")
        self.assertEqual(fields["likes_offset"], "0xFB4")
        self.assertEqual(fields["dislikes_offset"], "0xFC0")
        self.assertEqual(fields["like_slot_count"], 3)
        self.assertEqual(fields["dislike_slot_count"], 3)
        self.assertEqual(fields["native_skill_writer"], "0x455740")
        self.assertEqual(fields["native_mastery_evaluator"], "0x462500")
        self.assertEqual(
            fields["native_evaluator_scope"],
            "once per changed villager after exact-100 postverification",
        )

        payload = bytes.fromhex(
            next(
                item
                for item in feature.raw["patches"]
                if int(item["offset"], 0) == 0x7B820
            )["after"]
        )
        # VV3's writer takes delta + skill ordinal and returns with ret 8;
        # there must be no extra VV2 skill-code argument between them.
        self.assertIn(bytes.fromhex("506A008D8EAC0E0000"), payload)
        self.assertNotIn(bytes.fromhex("506A006A008D8EAC0E0000"), payload)

    def test_vv3_detail_mastery_is_exact_100_and_uses_native_handlers(self) -> None:
        source = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(
            encoding="utf-8"
        )
        detail = source.split("detail_mastery:", 1)[1].split(
            "detail_running:", 1
        )[0]
        for index in range(5):
            self.assertIn(f"push {index}", detail)
        self.assertIn("call 0x455740", detail)
        self.assertIn("call 0x462500", detail)
        for offset in ("0xEAC", "0xEB0", "0xEB4", "0xEB8", "0xEBC"):
            self.assertIn(f"cmp dword ptr [esi + {offset}], 100", detail)
        self.assertNotIn(", 90", detail)

    def test_vv3_running_requires_first_free_like_and_is_noop_when_already_present(self) -> None:
        source = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(
            encoding="utf-8"
        )
        detail = source.split("detail_running:", 1)[1].split(
            "detail_success:", 1
        )[0]
        self.assertIn("je running_already", detail)
        self.assertIn("mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}", detail)
        self.assertLess(
            detail.index("mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}"),
            detail.index("running_remove_dislikes:"),
        )
        self.assertIn("lea ecx, [edx + 0xFC0]", detail)
        self.assertIn("je running_already", source.split("running_preflight:", 1)[1])

    def test_vv3_cure_restores_health_below_80_and_clears_sickness(self) -> None:
        source = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(
            encoding="utf-8"
        )
        cure = source.split("cure_all:", 1)[1].split("preflight_code =", 1)[0]
        self.assertIn("cmp dword ptr [esi + 0xE78], 80", cure)
        self.assertIn("push 100", cure)
        self.assertIn("call 0x462670", cure)
        self.assertIn("cmp dword ptr [esi + 0xE78], 100", cure)
        self.assertIn("mov byte ptr [esi + 0xE89], 0", cure)
        self.assertIn("inc dword ptr [edi + 0x4FC]", cure)

    def test_vv3_tech_menu_marks_village_wide_rows_buyable(self) -> None:
        source = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("or dword ptr [esp + 0x10], 0xA01C0", source)
        self.assertIn("push -1\n            mov eax, dword ptr fs:[0]", source)
        self.assertIn("mov eax, dword ptr [esp + 4]\n            sub esp, 0x14", source)

    def test_vv3_release_keeps_menu_artifacts_and_excludes_duplicates(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"data/vv3_origins_village_wide_upgrades.json"', release)
        self.assertIn('"assets/origins/VVFP Origins Icons.dll"', release)
        for old in (
            "data/candidates/vv3_full_mastery_all_candidate.json",
            "data/candidates/vv3_individual_full_mastery_candidate.json",
            "data/candidates/vv3_individual_grant_running_candidate.json",
            "data/candidates/vv3_full_heal_cure_all_candidate.json",
            "VVFP VV3 Safe Upgrade Foundation.dll",
        ):
            self.assertNotIn(old, release)

    def test_vv3_companion_hash_matches_manifest(self) -> None:
        feature = get_fun_patch("vv3_enable_origins_exclusive_features")
        companion = feature.raw["companion_files"][0]
        path = ROOT / companion["source"]
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(), companion["sha256"]
        )


if __name__ == "__main__":
    unittest.main()
