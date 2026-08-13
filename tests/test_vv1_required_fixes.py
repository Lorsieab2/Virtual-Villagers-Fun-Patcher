import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import get_fun_patch, load_fun_patches  # noqa: E402


class VV1RequiredFixTests(unittest.TestCase):
    def test_only_current_vv1_origins_menu_routes_are_catalog_selectable(self) -> None:
        ids = {patch.id for patch in load_fun_patches()}
        self.assertNotIn("vv1_full_mastery_all_stage_a_candidate", ids)
        self.assertNotIn("vv1_individual_full_mastery_candidate", ids)
        self.assertNotIn("vv1_full_mastery_origins_composition", ids)
        self.assertIn("vv1_enable_origins_exclusive_features", ids)
        self.assertIn("vv1_origins_village_wide_upgrades", ids)

    def test_vv1_detail_menu_uses_four_slots_and_exact_mastery(self) -> None:
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        running = source.split("detail_menu,", 1)[1].split("detail_age_18:", 1)[0]
        self.assertIn("mov ecx, 4", running)
        self.assertIn("mov eax, 4", running)
        self.assertIn("lea ecx, [edx + 0x3A8]", running)

        mastery = source.split("detail_mastery:", 1)[1].split(
            "detail_success:", 1
        )[0]
        for offset in ("0x3BC", "0x3C0", "0x3C4", "0x3C8", "0x3CC"):
            self.assertIn(f"mov dword ptr [edx + {offset}], 100", mastery)
        self.assertNotIn("90", mastery)

    def test_vv1_cure_all_restores_partial_health_and_clears_sickness(self) -> None:
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        cure = source.split("cure_all:", 1)[1].split("cure_done:", 1)[0]
        self.assertIn("cmp dword ptr [edx + 0x344], 80", cure)
        self.assertIn("mov dword ptr [edx + 0x344], 100", cure)
        self.assertIn("mov byte ptr [edx + 0x354], 0", cure)

    def test_vv1_origins_maps_shr_and_defers_barrel_event(self) -> None:
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("SHR_FILE_OFFSET = 0x8B000", source)
        self.assertIn("SHR_RVA = 0x8D000", source)
        self.assertIn("CURE_ENTRY_VA = IMAGE_BASE + SHR_RVA", source)
        self.assertIn(
            "HEAL_CAVE_STUB_VA = IMAGE_BASE + SHR_RVA + (",
            source,
        )
        self.assertIn("rel32_jump(HEAL_CAVE_STUB_VA, CURE_ENTRY_VA)", source)
        self.assertIn("BARREL_PENDING_FILE_OFFSET = 0x8B700", source)
        self.assertIn("BARREL_MAIN_HELPER_FILE_OFFSET = 0x8B710", source)
        barrel = source.split("do_barrel:", 1)[1].split(
            "do_tech_doubler:", 1
        )[0]
        self.assertIn("mov byte ptr [0x{BARREL_PENDING_VA:X}], 1", barrel)
        self.assertIn("jmp menu_done", barrel)
        self.assertNotIn("call 0x42A6A0", barrel)

        feature = get_fun_patch("vv1_enable_origins_exclusive_features")
        offsets = {patch["offset"] for patch in feature.raw["patches"]}
        for offset in ("0x220", "0x270", "0x28C", "0x2403F", "0x8B700", "0x8B710"):
            self.assertIn(offset, offsets)
        self.assertEqual(
            next(p["after"] for p in feature.raw["patches"] if p["offset"] == "0x270"),
            "00100000",
        )
        self.assertEqual(
            next(p["after"] for p in feature.raw["patches"] if p["offset"] == "0x28C"),
            "600000F0",
        )

    def test_vv1_village_wide_payload_binds_four_slots_and_native_mastery(self) -> None:
        feature = get_fun_patch("vv1_origins_village_wide_upgrades")
        self.assertEqual(feature.raw["record_fields"]["like_slot_count"], 4)
        self.assertEqual(feature.raw["record_fields"]["dislike_slot_count"], 4)
        self.assertEqual(feature.raw["record_fields"]["native_skill_writer"], "0x437230")
        payload = bytes.fromhex(feature.raw["patches"][0]["after"])
        self.assertIn(b"\xB9\x04\x00\x00\x00", payload)
        running = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(
            encoding="utf-8"
        )
        full_like = running.split("running_full_like:", 1)[1].split(
            "running_existing:", 1
        )[0]
        self.assertIn("jmp running_next", full_like)

    def test_vv1_uses_a_dedicated_four_slot_companion(self) -> None:
        feature = get_fun_patch("vv1_enable_origins_exclusive_features")
        companion = feature.raw["companion_files"][0]
        self.assertEqual(companion["destination"], "VVFP VV1 Origins Icons.dll")
        path = ROOT / companion["source"]
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(), companion["sha256"]
        )
        native = (ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("#define VV_LIKE_SLOT_COUNT 4", native)
        self.assertIn("Already 4 likes.", native)

    def test_release_excludes_vv1_standalone_mastery_artifacts(self) -> None:
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"assets/origins/VVFP VV1 Origins Icons.dll"', release)
        self.assertNotIn('"data/candidates/vv1_full_mastery_all_candidate.json"', release)
        self.assertNotIn('"data/candidates/vv1_individual_full_mastery_candidate.json"', release)
        self.assertNotIn('"data/candidates/vv1_full_mastery_origins_composition.json"', release)


if __name__ == "__main__":
    unittest.main()
