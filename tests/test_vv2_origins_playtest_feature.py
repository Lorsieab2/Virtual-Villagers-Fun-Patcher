from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    VV2_PLAYTEST_DISABLED_FEATURE_ID,
    apply_patch,
    dry_run,
    load_fun_patches,
    load_builds,
    render_patched_bytes,
    _validate_playtest_output_request,
)


STOCK = ROOT / "research" / "stock-executables"


class VV2OriginsPlaytestFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.build = next(build for build in load_builds() if build.id == "vv2")
        self.source = STOCK / self.build.input_name

    def test_disabled_feature_is_not_in_normal_catalog(self) -> None:
        self.assertNotIn(
            VV2_PLAYTEST_DISABLED_FEATURE_ID,
            {patch.id for patch in load_fun_patches()},
        )

    def test_running_playtest_uses_direct_bounded_loop_not_old_result_callback(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8")
        )
        cure_patch = next(
            patch for patch in manifest["patches"] if patch["offset"] == "0x9A530"
        )
        payload = bytes.fromhex(cure_patch["after"])
        self.assertNotIn(b"\xFF\xD0", payload)
        self.assertIn(b"\x83\x3F\x26", payload)
        self.assertIn(b"\x3E\x00\x00\x00", payload)
        self.assertIn("running_village", (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(encoding="utf-8"))

    def test_explicit_playtest_render_is_marked_and_source_is_unchanged(self) -> None:
        before = self.source.read_bytes()
        rendered, applied = render_patched_bytes(
            self.source,
            self.build,
            "immediate_fixed",
            playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
        )
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(len(rendered), len(before))
        self.assertIn(f"feature:{VV2_PLAYTEST_DISABLED_FEATURE_ID}", {item["owner"] for item in applied})

    def test_payload_sections_are_mapped_and_runtime_vas_use_shr_rva(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8")
        )
        by_offset = {patch["offset"]: patch for patch in manifest["patches"]}
        self.assertEqual(by_offset["0x218"]["before"], "A8030200")
        self.assertEqual(by_offset["0x218"]["after"], "00100200")
        self.assertEqual(by_offset["0x234"]["before"], "40000040")
        self.assertEqual(by_offset["0x234"]["after"], "20000060")
        self.assertEqual(by_offset["0x268"]["before"], "04000000")
        self.assertEqual(by_offset["0x268"]["after"], "00100000")
        self.assertEqual(by_offset["0x284"]["before"], "400000D0")
        self.assertEqual(by_offset["0x284"]["after"], "600000F0")

        # Raw .shr offsets 0x9A009/0x9A530 map to VAs 0x49C009/0x49C530,
        # not IMAGE_BASE + raw_offset (the old 0x2000-displaced addresses).
        self.assertIn("80C14900", by_offset["0x9A009"]["after"])
        self.assertNotIn("80A14900", by_offset["0x9A009"]["after"])
        self.assertEqual(by_offset["0x9A004"]["after"], "E927050000")
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("mov ecx, edi", source)
        self.assertIn("mov edi, dword ptr [esi + 0x0C]", source)
        self.assertIn("call 0x425860", source)
        self.assertIn("cmp eax, 254", source)
        self.assertIn("push 10\n            push 21\n            call 0x433600", source)
        self.assertIn("This upgrade makes permanent changes to your village.", source)
        self.assertIn("The village population is already close to its max.", source)
        self.assertNotIn("[edi + 0x50AC]", source)

    def test_barrel_purchase_defers_native_event_until_tech_close(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8")
        )
        by_offset = {patch["offset"]: patch for patch in manifest["patches"]}
        payload = bytes.fromhex(
            by_offset["0x943A8"]["after"]
        )
        pending = payload.index(bytes.fromhex("803D00C7490000"))
        reservation = payload.index(bytes.fromhex("81ECD8500000"), pending)
        state = payload.index(bytes.fromhex("89F985C9"), reservation)
        nested_pool = payload.index(bytes.fromhex("83B9A405030000"), state)
        helper = payload.index(bytes.fromhex("E8CE10F9FF"), nested_pool)
        threshold = payload.index(bytes.fromhex("3DFE000000"), helper)
        funds = payload.index(bytes.fromhex("3987DCEA0200"), threshold)
        deduction = payload.index(bytes.fromhex("2987DCEA0200"), funds)
        cleanup = payload.index(bytes.fromhex("81C4D8500000"), deduction)
        purchased = payload.index(bytes.fromhex("B8D44D49005068B14D4900"), cleanup)
        token_store = payload.index(bytes.fromhex("C60500C7490001"), purchased)
        self.assertLess(pending, reservation)
        self.assertLess(reservation, state)
        self.assertLess(state, nested_pool)
        self.assertLess(nested_pool, helper)
        self.assertLess(helper, threshold)
        self.assertLess(threshold, funds)
        self.assertLess(funds, deduction)
        self.assertLess(deduction, cleanup)
        self.assertLess(cleanup, purchased)
        self.assertLess(purchased, token_store)
        self.assertNotIn(bytes.fromhex("8B8FA4500000"), payload[pending:helper])
        self.assertNotIn(bytes.fromhex("682C1A4B7F6A02"), payload[pending:0x500])
        self.assertEqual(payload.count(bytes.fromhex("6A0A6A15E805E9F9FFC20800")), 1)
        self.assertEqual(by_offset["0x9A700"]["before"], "00")
        self.assertEqual(by_offset["0x9A700"]["after"], "00")
        self.assertEqual(
            by_offset["0x9A710"]["after"],
            "8B4E146A4BE8F628FAFF6A008BCEE8CDF0F6FF8B460C"
            "C7807004030001000000803D00C74900007436C60500C7490000"
            "81ECD8500000682C1A4B7F6A028D4C2408E88A81F9FF"
            "6A00568D4C2408E86E53F6FF89E1E8276AF9FF"
            "81C4D8500000E98670FAFF",
        )
        self.assertEqual(by_offset["0x437DA"]["before"], "8B4E146A4B")
        self.assertEqual(by_offset["0x437DA"]["after"], "E9318F0500")

    def test_detail_upgrades_button_is_nudged_right_without_behavior_changes(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        detail = source[
            source.index("        detail_constructor,") :
            source.index("        show_dialog,")
        ]
        self.assertIn(
            "            push 0\n"
            "            push esi\n"
            "            push 563\n"
            "            push 136\n"
            "            push 0x4763E8\n"
            "            push 6\n"
            "            mov ecx, eax\n"
            "            call 0x4019D0",
            detail,
        )
        self.assertNotIn("            push 120\n", detail)
        self.assertIn("            call 0x40B560", detail)
        manifest = json.loads(
            (ROOT / "data" / "vv2_origins_feature.json").read_text(encoding="utf-8")
        )
        payload = bytes.fromhex(
            next(patch for patch in manifest["patches"] if patch["offset"] == "0x943A8")[
                "after"
            ]
        )
        self.assertEqual(
            payload.count(bytes.fromhex("6A00566833020000688800000068E86347006A06")),
            1,
        )
        self.assertNotIn(bytes.fromhex("6A005668330200006A7868E86347006A06"), payload)

    def test_dry_run_marks_separate_playtest_output(self) -> None:
        result = dry_run(
            self.source,
            "immediate_fixed",
            playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
            output_root=Path("C:/Users/Owner/Downloads"),
        )
        self.assertTrue(result["playtest_only"])
        self.assertEqual(result["fun_patches"], [VV2_PLAYTEST_DISABLED_FEATURE_ID])
        self.assertTrue(result["output_name"].endswith("Modded Playtest.exe"))
        self.assertEqual(result["absolute_maximum"], 256)

    def test_unknown_or_mixed_playtest_selection_is_rejected(self) -> None:
        with self.assertRaisesRegex(PatcherError, "Only the disabled VV2 Origins"):
            render_patched_bytes(
                self.source,
                self.build,
                "immediate_fixed",
                playtest_disabled_feature_ids=["unknown-feature"],
            )
        with self.assertRaisesRegex(PatcherError, "cannot be combined"):
            render_patched_bytes(
                self.source,
                self.build,
                "immediate_fixed",
                ["vv2_birth_control"],
                playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
            )

    def test_mixed_playtest_selection_requires_distinct_absolute_root(self) -> None:
        with self.assertRaisesRegex(PatcherError, "distinct explicit playtest output root"):
            _validate_playtest_output_request(
                fun_patch_ids=["vv2_birth_control"],
                playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
                output_root=None,
                playtest_output_root=None,
            )
        with self.assertRaisesRegex(PatcherError, "absolute path"):
            _validate_playtest_output_request(
                fun_patch_ids=["vv2_birth_control"],
                playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
                output_root=None,
                playtest_output_root=Path("relative-playtest-root"),
            )
        _validate_playtest_output_request(
            fun_patch_ids=["vv2_birth_control"],
            playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
            output_root=None,
            playtest_output_root=Path("C:/Users/Owner/Downloads/vv2-stress"),
        )

    def test_apply_requires_explicit_output_root_and_rejects_save_copy(self) -> None:
        with self.assertRaisesRegex(PatcherError, "explicit output root"):
            apply_patch(
                self.source,
                "immediate_fixed",
                playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
            )
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(PatcherError, "cannot copy or replace saves"):
                apply_patch(
                    self.source,
                    "immediate_fixed",
                    output_root=Path(temp),
                    copy_saves=True,
                    playtest_disabled_feature_ids=[VV2_PLAYTEST_DISABLED_FEATURE_ID],
                )


if __name__ == "__main__":
    unittest.main()
