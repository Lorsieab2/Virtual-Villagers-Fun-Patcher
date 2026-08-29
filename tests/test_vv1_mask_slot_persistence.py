"""Structural gates for VV1 mask slot capture and sidecar isolation.

These tests deliberately stop at source/manifest/byte-layout evidence. They
do not claim that a running game restores a mask or that a held mask is
player-visible; the exact stock pickup-to-central-render call chain and its
player/runtime gates are documented in ``docs/vv1-mask-pickup-static-audit.md``.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_CAPSTONE = False

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SOURCE = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
GENERATOR = ROOT / "scripts" / "build_vv1_origins_feature.py"
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"
AUDIT = ROOT / "docs" / "vv1-mask-pickup-static-audit.md"
EXPORTS = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.def"
STOCK_CANDIDATES = (
    ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe",
    ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe",
)


def _stock() -> Path | None:
    return next((path for path in STOCK_CANDIDATES if path.is_file()), None)


class VV1MaskSlotSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.generator = GENERATOR.read_text(encoding="utf-8")
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.patches = {
            int(item["offset"], 0): item for item in cls.manifest["patches"]
        }
        cls.exports = EXPORTS.read_text(encoding="utf-8")
        cls.audit = AUDIT.read_text(encoding="utf-8")

    def test_slot_capture_constants_and_sidecar_path_are_exact(self) -> None:
        self.assertIn(
            "#define VV_MASK_SAVE_SLOT (*(unsigned int *)(VV_MASK_SCRATCH_BASE + 0x1F4))",
            self.source,
        )
        self.assertIn("#define VV_MASK_FIRST_SAVE_SLOT 1", self.source)
        self.assertIn("#define VV_MASK_LAST_SAVE_SLOT 5", self.source)
        self.assertIn("vv1_masks_%u.dat", self.source)
        self.assertNotIn("vv1_masks.dat", self.source)
        self.assertNotIn("vv1_masks.dat", self.generator)
        self.assertIn("MASK_SAVE_SLOT_VA = DATA_SCRATCH_BASE_VA + 0x1F4", self.generator)

    def test_slot_change_clears_table_and_latches_before_loading(self) -> None:
        self.assertIn("static int vv1_mask_loaded_slot = -1;", self.source)
        self.assertIn("if (slot != vv1_mask_loaded_slot)", self.source)
        self.assertIn("vv1_mask_clear_state();", self.source)
        self.assertIn("memset(VV_MASK_TABLE, 0, VV_MASK_TABLE_BYTES);", self.source)
        self.assertIn("memset(vv1_mask_seen_alive, 0, sizeof(vv1_mask_seen_alive));", self.source)
        self.assertIn("if (!vv1_mask_prepare_slot())", self.source)
        self.assertIn("if (!slot || !vv1_mask_sidecar_path(path, sizeof(path), slot))", self.source)

    def test_dead_sweep_still_persists_clears(self) -> None:
        self.assertIn("swept = vv1_mask_sweep_dead();", self.source)
        self.assertIn("if (swept) {", self.source)
        self.assertIn("vv1_mask_sidecar_save();", self.source)

    def test_live_frame_tick_sweeps_and_persists_only_actual_clears(self) -> None:
        self.assertIn("Vv1MaskTick=_Vv1MaskTick@0", self.exports)
        start = self.source.index(
            "__declspec(dllexport) void __stdcall Vv1MaskTick(void)"
        )
        end = self.source.index("static HINSTANCE module_instance;", start)
        tick = self.source[start:end]
        for token in (
            "if (!vv1_mask_prepare_slot())",
            "swept = vv1_mask_sweep_dead();",
            "if (swept)",
            "vv1_mask_sidecar_save();",
        ):
            with self.subTest(token=token):
                self.assertIn(token, tick)
        self.assertIn("call {MASK_TICK_STUB_VA:#x}", self.generator)
        self.assertIn("MASK_TICK_DLL_FN_VA = DATA_SCRATCH_BASE_VA + 0x1F8", self.generator)

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_manifest_calls_cached_tick_from_the_live_frame_hook(self) -> None:
        name = bytes.fromhex(self.patches[0x8E8F0]["after"])
        self.assertEqual(name, b"Vv1MaskTick\0")

        tick = bytes.fromhex(self.patches[0x8E900]["after"])
        tick_ins = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(tick, 0x490900))
        tick_shape = [(item.mnemonic, item.op_str) for item in tick_ins]
        self.assertEqual(tick_shape[0], ("pushal", ""))
        self.assertIn(("cmp", "eax, 1"), tick_shape)
        sentinel_check = tick_shape.index(("cmp", "eax, 1"))
        self.assertEqual(tick_shape[sentinel_check + 1][0], "je")
        self.assertIn(("call", "eax"), tick_shape)
        self.assertIn(("mov", "dword ptr [0x4911f8], 1"), tick_shape)
        self.assertEqual(tick_shape[-2:], [("popal", ""), ("ret", "")])

        frame = bytes.fromhex(self.patches[0x8E400]["after"])
        frame_ins = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(frame, 0x490400))
        calls = {
            int(item.op_str, 16)
            for item in frame_ins
            if item.mnemonic == "call" and item.op_str.startswith("0x")
        }
        self.assertIn(0x490900, calls)
        restore_index = next(
            index
            for index, item in enumerate(frame_ins)
            if item.mnemonic == "call" and item.op_str == "0x4906c0"
        )
        tick_index = next(
            index
            for index, item in enumerate(frame_ins)
            if item.mnemonic == "call" and item.op_str == "0x490900"
        )
        self.assertLess(restore_index, tick_index)
        self.assertEqual(frame_ins[restore_index - 1].mnemonic, "jne")
        self.assertEqual(
            int(frame_ins[restore_index - 1].op_str, 16),
            frame_ins[tick_index].address,
        )

    def test_occupied_dead_forall_policy_is_an_explicit_evidence_boundary(self) -> None:
        for token in (
            "record+0x28 == 1",
            "dead-but-not-yet-freed record",
            "deliberately unchanged",
            "parity/evidence boundary",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.audit)

    def test_pickup_audit_records_central_render_boundary(self) -> None:
        audit = self.audit
        for token in (
            "0x4392D0",
            "0x425226",
            "0x439410",
            "0x425937",
            "0x423FD1",
            "0x424090",
            "0x437790",
            "0x43741B",
            "0x4374A4",
            "0x437503",
            "0x437556",
            "No pickup hook\nwas added.",
            "runtime/save results remain unverified",
        ):
            with self.subTest(token=token):
                self.assertIn(token, audit)
        self.assertIn(
            "static: held villagers update the ordinary record position",
            self.manifest["mask_persistence"]["pickup_held_runtime_status"],
        )

    def test_exact_save_builder_preimage_and_owned_append_are_manifest_bound(self) -> None:
        patches = {item["offset"]: item for item in self.manifest["patches"]}
        splice = patches["0x2ED0"]
        self.assertEqual(splice["before"], "8B4424048B11")
        self.assertEqual(len(bytes.fromhex(splice["after"])), 6)
        self.assertTrue(splice["after"].endswith("90"))
        cave = patches["0x8E820"]
        self.assertEqual(len(bytes.fromhex(cave["after"])), 129)
        self.assertEqual(bytes.fromhex(cave["after"])[0], 0x60)  # pushad
        self.assertIn("capture the exact VV1 save-slot argument", cave["purpose"])

        tx = self.manifest["pe_append_transaction"]
        self.assertEqual(tx["section_name"], ".vv1mc/.vv1md")
        self.assertEqual(tx["append_length"], 0x2000)
        for mode in ("collection_progression", "immediate_fixed"):
            with self.subTest(mode=mode):
                layout = tx["layouts"][mode]
                self.assertEqual(int(layout["original_file_size"], 0), 0x8E000)
                self.assertEqual(int(layout["append_offset"], 0), 0x8E000)
                self.assertEqual(layout["append_length"], 0x2000)
                self.assertEqual(len(bytes.fromhex(layout["append_bytes"])), 0x2000)
                self.assertEqual(
                    [item["offset"] for item in layout["header_patches"]],
                    ["0xFE", "0x148", "0x2B8", "0x2E0"],
                )

    @unittest.skipUnless(_stock() is not None, "needs the local ignored VV1 stock executable")
    def test_normal_renderer_owns_and_applies_both_mask_sections(self) -> None:
        import vv_fun_patcher as patcher

        source = _stock()
        assert source is not None
        build = patcher.identify(source)
        feature = next(
            item
            for item in patcher.load_fun_patches()
            if item.id == "vv1_enable_origins_exclusive_features"
        )
        rendered, _ = patcher.render_patched_bytes(
            source,
            build,
            "collection_progression",
            [feature.id],
        )
        self.assertEqual(len(rendered), 0x90000)
        immediate, _ = patcher.render_patched_bytes(
            source,
            build,
            "immediate_fixed",
            [feature.id],
        )
        self.assertEqual(len(immediate), 0x90000)
        data = bytes(rendered)
        lf = struct.unpack_from("<I", data, 0x3C)[0]
        self.assertEqual(struct.unpack_from("<H", data, lf + 6)[0], 7)
        opt = lf + 0x18
        self.assertEqual(struct.unpack_from("<I", data, opt + 0x38)[0], 0x92000)
        table = opt + struct.unpack_from("<H", data, lf + 0x14)[0]
        sections = {
            data[table + i * 0x28 : table + i * 0x28 + 8].rstrip(b"\0").decode():
            data[table + i * 0x28 : table + (i + 1) * 0x28]
            for i in range(7)
        }
        self.assertIn(".vv1mc", sections)
        self.assertIn(".vv1md", sections)
        self.assertEqual(struct.unpack_from("<I", sections[".vv1mc"], 12)[0], 0x90000)
        self.assertEqual(struct.unpack_from("<I", sections[".vv1md"], 12)[0], 0x91000)
        self.assertEqual(struct.unpack_from("<I", sections[".vv1mc"], 20)[0], 0x8E000)
        self.assertEqual(struct.unpack_from("<I", sections[".vv1md"], 20)[0], 0x8F000)

        # The splice is the two complete native loads, followed by a NOP to
        # make the five-byte JMP overwrite length explicit.
        self.assertEqual(data[0x2ED0], 0xE9)
        self.assertEqual(data[0x2ED5], 0x90)
        displacement = struct.unpack_from("<i", data, 0x2ED1)[0]
        self.assertEqual(0x402ED0 + 5 + displacement, 0x490820)
        self.assertEqual(data[0x8E820], 0x60)  # pushad in the owned cave
        self.assertIn(b"\x8B\x44\x24\x24", data[0x8E820 : 0x8E820 + 129])
        self.assertIn(b"\xA3\xF4\x11\x49\x00", data[0x8E820 : 0x8E820 + 129])

        # Removal must unwind the ordinary feature bytes, truncate only the
        # exact owned tail, and restore the mode-specific pre-feature parent.
        for mode, installed in (
            ("collection_progression", rendered),
            ("immediate_fixed", immediate),
        ):
            with self.subTest(remove_mode=mode):
                parent, _ = patcher.render_patched_bytes(source, build, mode, [])
                removed = bytearray(installed)
                patcher._remove_feature_bytes(removed, feature, mode)
                self.assertEqual(bytes(removed), bytes(parent))


if __name__ == "__main__":
    unittest.main()
