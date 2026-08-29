from __future__ import annotations

import hashlib
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"
SYNC_BUILDER = ROOT / "scripts" / "build_vv3_safe_upgrade_resources.py"
AUDIT = ROOT / "docs" / "vv3-mask-rendering-repair-audit.md"


def _load_sync_builder():
    spec = importlib.util.spec_from_file_location("vv3_safe_upgrade_sync", SYNC_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load VV3 companion synchronizer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VV3MaskRenderingRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.native = NATIVE.read_text(encoding="utf-8")
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.audit = AUDIT.read_text(encoding="utf-8")
        cls.sync_builder = _load_sync_builder()

    def test_invalid_head_callback_clears_both_render_stashes(self) -> None:
        clear = self.native.split("static void vv3_mask_clear_render_stashes", 1)[1]
        clear = clear.split("/* Draw the world mask", 1)[0]
        self.assertIn("g_vv3_stash_valid = 0;", clear)
        self.assertIn("g_vv3_action_seen = 0;", clear)
        callback = self.native.rsplit(
            "__declspec(dllexport) void __stdcall VV3WorldMaskDrawAt", 1
        )[1]
        callback = callback.split("/* ================= Change Appearance", 1)[0]
        invalid = callback[callback.index("if (record == NULL || args == NULL) {") :]
        invalid = invalid[: invalid.index("return;")]
        self.assertIn("vv3_mask_clear_render_stashes();", invalid)

    def test_active_synchronizer_rejects_unpinned_source_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "candidate.dll"
            target = Path(folder) / "safe-upgrades.dll"
            source.write_bytes(b"wrong canonical bytes")
            target.write_bytes(b"keep existing deployed copy")
            with patch.object(self.sync_builder, "SOURCE", source), patch.object(
                self.sync_builder, "OUTPUT", target
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "source fingerprint mismatch"
                ):
                    self.sync_builder.synchronize()
            self.assertEqual(target.read_bytes(), b"keep existing deployed copy")

    def test_details_uses_current_full_cell_lift(self) -> None:
        self.assertIn("#define VV3_MASK_LIFT_MUL 18", self.native)
        self.assertIn(
            "ymask   = args[2] - ((scaledY * VV3_MASK_LIFT_MUL) >> 7);",
            self.native,
        )
        self.assertIn("200*18>>7 == 28", self.audit)

    def test_world_path_replays_exact_head_tuple_with_retained_colour_seats(self) -> None:
        world = self.native.split("__declspec(dllexport) void __stdcall VV3WorldMaskDraw(int index)", 1)[1]
        self.assertIn("x = g_vv3_stash_x;", world)
        self.assertIn("y = g_vv3_stash_y;", world)
        self.assertIn("g_vv3_color_dy[cidx]", world)
        self.assertIn("liftsc", world)
        self.assertIn("g_vv3_stash_m3010", world)
        self.assertIn("mov  eax, one", world)
        self.assertNotIn("g_vv3_facing_dx[facing & 7]", world)
        self.assertNotIn("mov  eax, scaleBits", world)
        self.assertIn("*p3010 = save3010;", world)
        self.assertRegex(
            self.native,
            r"int g_vv3_facing_dx\[8\]\s*=\s*\{\s*0, 0, 0, 0, 0, 0, 0, 0\s*\};",
        )
        self.assertRegex(
            self.native,
            r"int g_vv3_color_dy\[5\]\s*=\s*\{\s*41, 40, 37, 35, 32\s*\};",
        )

    def test_action_is_stash_only_and_final_owner_is_fail_closed(self) -> None:
        action_start = self.native.index(
            "__declspec(dllexport) void __stdcall VV3ActionMaskDraw",
            self.native.index("/* ACTION-POSE stash"),
        )
        action = self.native[action_start:]
        action = action.split("/* Head-site STASH", 1)[0]
        world = self.native.split("__declspec(dllexport) void __stdcall VV3WorldMaskDraw(int index)", 1)[1]
        world = world.split("/* ACTION-POSE stash", 1)[0]
        self.assertIn("g_vv3_action_seen", action)
        self.assertIn("g_vv3_action_anim = *(int *)", action)
        self.assertIn("g_vv3_action_seen = (g_vv3_action_anim == -1) ? 0 : 1", action)
        self.assertNotIn("VV3_GetMaskForRecord", action)
        self.assertNotIn("VV3_WORLD_DRAW_FN", action)
        self.assertIn("if (held)", world)
        self.assertIn("} else if (action_match)", world)
        self.assertIn("action_anim < 0 || action_anim > 50", world)
        self.assertIn("goto world_mask_cleanup", world)
        self.assertIn("vv3_mask_clear_render_stashes();", self.native)

    def test_both_stock_action_call_sites_target_the_one_wrapper(self) -> None:
        self.assertIn("WORLD_ACTION_CALLSITE_VA = 0x00460B48", self.builder)
        self.assertIn('WORLD_ACTION_CALLSITE_BEFORE = bytes.fromhex("E893ECFFFF")', self.builder)
        self.assertIn("WORLD_ACTION_CALLSITE_SECOND_VA = 0x00460D10", self.builder)
        self.assertIn('WORLD_ACTION_CALLSITE_SECOND_BEFORE = bytes.fromhex("E8CBEAFFFF")', self.builder)
        self.assertIn("world_action_wrap_redirect_second", self.builder)
        self.assertIn("WORLD_ACTION_WRAP_CAVE_VA = SECTION_CODE_VA + 0x0C0", self.builder)
        self.assertIn("if WORLD_ACTION_WRAP_CAVE_VA + len(world_action_wrap_cave)", self.builder)
        self.assertIn("F14_ROUTING", self.builder)
        self.assertIn("WORLD_ACTION_CALLSITE_VA = 0x00460B48", self.builder)
        self.assertIn("WORLD_HANDLER_CALLSITE_VA = 0x0042E3F5", self.builder)
        self.assertNotIn("put(0x434357", self.builder)
        self.assertNotIn("put(0x4344B3", self.builder)

    def test_audit_records_exact_stock_identity_and_proven_ownership(self) -> None:
        self.assertIn("8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503", self.audit)
        self.assertIn("0x434357", self.audit)
        self.assertIn("0x4344B3", self.audit)
        self.assertIn("Generic task-1 swimming on terrain 5 remains head-owned", self.audit)
        self.assertIn("Fishing\ntask 11 frames `8` and `9`", self.audit)
        self.assertIn("Visual placement remains pending player acceptance", self.audit)

    def test_canonical_atlas_geometry_and_resource_are_pinned(self) -> None:
        atlas = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png"
        blob = atlas.read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest().upper(), "EFA9DF82A4DF0BAB11104C7E1757BFDEF95BF7D07E5EBE4C75566DEC56B01FBE")
        self.assertEqual(struct.unpack(">II", blob[16:24]), (520, 725))
        rc = (ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.rc").read_text(encoding="utf-8")
        self.assertIn("5000 RCDATA", rc)
        self.assertIn("../../assets/vv3_heathen_masks/heathen_masks.png", rc)

    def test_retired_atlas_builders_are_fail_closed(self) -> None:
        atlas = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png"
        before = atlas.read_bytes()
        for name, args in (
            ("build_vv3_mask_atlas.py", ["Images"]),
            ("build_vv3_mask_atlas_separate.py", []),
        ):
            builder = ROOT / "scripts" / name
            source = builder.read_text(encoding="utf-8")
            self.assertIn("520x725", source)
            self.assertNotIn("320x640", source)
            self.assertNotIn("Image.new", source)
            result = subprocess.run(
                [sys.executable, str(builder), *args],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no file written", result.stdout)
            self.assertEqual(atlas.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
