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

    def test_inline_head_callback_reuses_only_the_authoritative_tuple(self) -> None:
        callback = self.native.split(
            "__declspec(dllexport) void __stdcall VV3WorldMaskDrawAt", 1
        )[1].split("/* ================= Change Appearance", 1)[0]
        self.assertIn("for (i = 0; i < 6; ++i) mask_args[i] = args[i];", callback)
        self.assertIn("mask_args[0] = (int)(UINT_PTR)atlas;", callback)
        self.assertIn("mask_args[3] = mask - 1;", callback)
        self.assertIn("held (`+0xF12`) branch rejoins", callback)
        self.assertNotIn("F12) != 0) return", callback)
        self.assertIn("VV3_WORLD_HEAD_DRAW_FN", callback)
        self.assertNotIn("g_vv3_stash", self.native)
        self.assertNotIn("VV3ActionMaskDraw", self.native)
        self.assertNotIn("VV3WorldMaskDraw(int index)", self.native)

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

    def test_world_path_uses_the_true_head_callsite_and_six_arguments(self) -> None:
        self.assertIn("WORLD_MASK_CALLSITE_VA = 0x460C7F", self.builder)
        self.assertIn("WORLD_HEAD_DRAW_VA = 0x42E5E0", self.builder)
        self.assertIn("WORLD_MASK_CAVE_VA = SECTION_CODE_VA + 0x000", self.builder)
        cave = self.builder.split("world_mask_cave = assemble", 1)[1].split(
            "world_mask_head_redirect", 1
        )[0]
        self.assertEqual(cave.count("push dword ptr [esp + 0x18]"), 6)
        self.assertIn("call 0x{WORLD_HEAD_DRAW_VA:X}", cave)
        self.assertIn("lea edx, [esp + 4]", cave)
        self.assertIn("ret 0x18", cave)
        self.assertNotIn("WORLD_MASK_CALLSITE_VA = 0x460A60", self.builder)
        self.assertNotIn("0x460A60", self.native)

    def test_details_jmp_cave_replays_the_original_seven_argument_stack(self) -> None:
        cave = self.builder.split("        MASK_CAVE_VA,", 1)[1].split(
            "    mask_hook_code =", 1
        )[0]
        # The detour is a JMP from after the seven stock pushes, so the cave
        # has no synthetic return address and [esp+0x18] is the seventh arg.
        self.assertEqual(cave.count("push dword ptr [esp + 0x18]"), 7)
        self.assertIn("mov edx, esp", cave)
        self.assertIn("add esp, 0x1C", cave)
        self.assertNotIn("lea edx, [esp + 4]", cave)

    def test_dllmain_publishes_vv3md_slots_only_after_writable_page_probe(self) -> None:
        self.assertIn("static BOOL vv3_mask_data_page_writable(void)", self.native)
        self.assertIn("VirtualQuery", self.native)
        self.assertIn("info.State != MEM_COMMIT", self.native)
        self.assertIn("info.RegionSize", self.native)
        self.assertIn("PAGE_READWRITE", self.native)
        dllmain = self.native.split("BOOL WINAPI DllMain", 1)[1].split(
            "/* ---- Heathen-mask overlay atlas", 1
        )[0]
        self.assertIn("if (!vv3_mask_data_page_writable()) return TRUE;", dllmain)
        publication = dllmain.split(
            "if (!vv3_mask_data_page_writable()) return TRUE;", 1
        )[1]
        self.assertIn("VV3_WORLD_DRAWFN_PTR_SLOT", publication)

    def test_action_paths_remain_stock_and_no_reconstruction_hook_is_emitted(self) -> None:
        self.assertNotIn("WORLD_ACTION", self.builder)
        self.assertNotIn("VV3ActionMaskDraw", self.native)
        self.assertNotIn("VV3ActionMaskDraw", (ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.def").read_text(encoding="utf-8"))
        self.assertNotIn("0x460B48", self.builder)
        self.assertNotIn("0x460D10", self.builder)

    def test_handler_and_action_call_sites_are_not_mask_hooks(self) -> None:
        self.assertNotIn("WORLD_HANDLER_CALLSITE_VA", self.builder)
        self.assertNotIn("WORLD_ACTION_CALLSITE_VA", self.builder)
        self.assertNotIn("put(0x434357", self.builder)
        self.assertNotIn("put(0x4344B3", self.builder)
        manifest = __import__("json").loads(
            (ROOT / "data" / "vv3_origins_feature.json").read_text(encoding="utf-8")
        )
        offsets = {int(item["offset"], 0) for item in manifest["patches"]}
        self.assertNotIn(0x2E3F5, offsets)
        self.assertNotIn(0x60B48, offsets)
        self.assertNotIn(0x60D10, offsets)

    def test_audit_records_exact_stock_identity_and_proven_ownership(self) -> None:
        self.assertIn("8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503", self.audit)
        self.assertIn("0x434357", self.audit)
        self.assertIn("0x4344B3", self.audit)
        self.assertIn("Generic task-1 swimming on terrain 5", self.audit)
        self.assertIn("task-11 fishing\nframes `8`/`9` remain stock action/head ownership", self.audit)
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
