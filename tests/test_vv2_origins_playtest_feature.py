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
        self.assertEqual(
            hashlib.sha256(rendered).hexdigest().upper(),
            "371058CEE9428CF787E09252AF086013E7FBAE1B2503091AA096BF8F8A26FE59",
        )
        self.assertIn(
            f"feature:{VV2_PLAYTEST_DISABLED_FEATURE_ID}",
            {item["owner"] for item in applied},
        )

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
