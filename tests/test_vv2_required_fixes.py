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
        # The village-wide rows run in the companion (ApplyVV2RunningToAll,
        # ApplyVV2MasteryToAll, ApplyVV2AgeToAll, reached through the dispatch
        # stub); the payload that used to carry this layout as ABI metadata
        # was unreachable and is gone (#506 review), so its route record
        # carries none. The layout is bound where the rows actually run.
        feature = get_fun_patch("vv2_origins_village_wide_upgrades")
        self.assertEqual(feature.raw["patches"], [])
        self.assertNotIn("record_fields", feature.raw)
        self.assertNotIn("extension_abi", feature.raw)
        native = (ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c").read_text(
            encoding="utf-8"
        )
        for line in (
            "#define VV2_SPECIAL_OFFSET  0x558",
            "#define VV2_LIKES_OFFSET    0x5F0",
            "#define VV2_DISLIKES_OFFSET 0x6E8",
            "#define VV2_PREF_SLOTS      62",
        ):
            self.assertIn(line, native)
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(encoding="utf-8")
        # The dispatch stub hands each row the record base the game's own
        # singleton getter returns.
        self.assertIn('running_export_bytes = b"ApplyVV2RunningToAll\\0"', source)
        self.assertIn('mastery_export_bytes = b"ApplyVV2MasteryToAll\\0"', source)
        self.assertIn("call 0x44F4E0", source)

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
        # The skill-code table (2, 5, 1, 3, 4) only the removed village-wide
        # payload read is gone with it (#506 review).
        self.assertNotIn("vv2_skill_codes", source)
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
        # PR #30 contract: Running is added to the first free Like slot, and
        # any Running Dislike is removed whether or not a Like was added (so a
        # full-Like villager still gets the dislike cleared for free); only
        # already-Running villagers are truly left unchanged.
        self.assertIn("removes any Running Dislike whether or not a Like was added", village)
        self.assertIn("leaves already-Running villagers unchanged", village)
        # The generic branch (A New Home and The Secret City reach it; The
        # Lost Children's village-wide rows run in its companion now). The
        # old 16-space form matched only New Believers' native branch,
        # removed with its unreachable payload.
        self.assertIn("running_existing:\n            inc ebp\n            jmp running_next", village)

    def test_vv2_cure_all_restores_partial_health_and_clears_sickness(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        # Cure is the whole helper now: the menu calls it directly (#506
        # review removed the rows 6-8 dispatch in front of it).
        cure = source.split("cure_code = assemble(", 1)[1].split("cure_report:", 1)[0]
        # Cure All is a full heal: any living villager below full health
        # (100) is restored to 100, and sickness (+0x53C) is cleared.
        self.assertIn("cmp dword ptr [edx + 0x52C], 100", cure)
        self.assertIn("mov dword ptr [edx + 0x52C], 100", cure)
        self.assertIn("mov dword ptr [edx + 0x53C], 0", cure)

    def test_vv2_tech_dialog_marks_rows_six_to_eight_as_buyable(self) -> None:
        # The whole-village rows (6-8) are kept buyable by the dialog proc,
        # not by a payload dialog-state mask: when the village-wide-buy state
        # is set the proc forces those rows to "Buy" + enabled instead of the
        # "Remove"/"Unavailable"/"Done" states the other rows use.
        native = (ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("STATE_VILLAGE_WIDE_BUY = 0x80000", native)
        self.assertIn("village_wide_buy && row >= 6", native)
        self.assertIn('SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy")', native)
        self.assertIn(
            "EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE)", native
        )

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
