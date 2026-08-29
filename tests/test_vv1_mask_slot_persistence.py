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

    def test_corrupt_sidecar_nibbles_fail_closed_at_shared_mask_accessor(self) -> None:
        start = self.source.index("static unsigned char vv1_mask_get(")
        end = self.source.index("static void vv1_mask_set(", start)
        getter = self.source[start:end]
        self.assertIn("value = (index & 1)", getter)
        self.assertIn("return (value < VV_MASK_COUNT) ? value : 0;", getter)
        self.assertIn(
            "Sidecars are external, user-writable input.  A corrupt high nibble",
            getter,
        )

    def test_newborn_reuse_clears_at_exact_allocator_boundary(self) -> None:
        patches = {int(item["offset"], 0): item for item in self.manifest["patches"]}
        splice = patches[0x3C393]
        self.assertEqual(splice["before"], "C6462801C6462900")
        self.assertEqual(len(bytes.fromhex(splice["after"])), 8)
        cave = patches[0x8EA00]
        self.assertIn("sub_43C350", cave["purpose"])
        self.assertIn("newborn", cave["purpose"])
        self.assertIn("MASK_NEWBORN_CLEAR_FILE_OFFSET", self.generator)
        self.assertIn("MASK_BIRTH_DIRTY_VA = DATA_SCRATCH_BASE_VA + 0x1FC", self.generator)
        self.assertIn("mov byte ptr [0x{MASK_BIRTH_DIRTY_VA:X}], 1", self.generator)
        self.assertIn("C605FC11490001", cave["after"])
        self.assertIn("mov ecx, dword ptr [esp + 0x30]", self.generator)
        self.assertIn("MASK_NEWBORN_CLEAR_RESUME_VA = 0x43C39B", self.generator)
        self.assertIn(
            "exact sub_43C350 allocation boundary at 0x43C393",
            self.manifest["mask_persistence"]["newborn_reuse_guard"],
        )
        self.assertIn("persist the clear", self.manifest["mask_persistence"]["newborn_reuse_guard"])

    def test_newborn_cave_final_jump_decodes_from_recorded_section_mapping(self) -> None:
        """The emitted cave must return to the exact post-splice instruction.

        ``append_bytes`` is intentionally zero-filled because the ordinary
        patch list supplies the cave payload.  Decode the recorded ``.vv1mc``
        section header (RVA + raw file pointer), map the emitted cave's raw
        offset into its runtime VA, and then decode the final E9 from the
        manifest payload.  Using the raw file offset as an RVA would produce
        a plausible-looking but wrong target (the regression this gate is
        meant to prevent).
        """
        tx = self.manifest["pe_append_transaction"]
        layout = tx["layouts"]["collection_progression"]
        section_patch = next(
            item
            for item in layout["header_patches"]
            if item["offset"] == "0x2B8"
        )
        header = bytes.fromhex(section_patch["after"])
        self.assertEqual(header[:8], b".vv1mc\0\0")
        section_rva = struct.unpack_from("<I", header, 12)[0]
        section_raw = struct.unpack_from("<I", header, 20)[0]
        self.assertEqual(section_rva, 0x90000)
        self.assertEqual(section_raw, 0x8E000)

        cave_item = next(
            item for item in self.manifest["patches"] if item["offset"] == "0x8EA00"
        )
        cave = bytes.fromhex(cave_item["after"])
        cave_raw = int(cave_item["offset"], 0)
        cave_va = 0x400000 + section_rva + (cave_raw - section_raw)
        self.assertEqual(cave_va, 0x490A00)
        self.assertGreaterEqual(len(cave), 5)
        self.assertEqual(cave[-5], 0xE9)
        displacement = struct.unpack_from("<i", cave, len(cave) - 4)[0]
        final_target = cave_va + len(cave) + displacement
        self.assertEqual(final_target, 0x43C39B)

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
            "if (swept || birth_dirty)",
            "if (vv1_mask_sidecar_save())",
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

    def test_sidecar_write_is_transactional_and_preserves_final_format(self) -> None:
        write = self.source.split("static int vv1_mask_sidecar_save(void) {", 1)[1].split(
            "static void vv1_mask_sidecar_load(void) {", 1
        )[0]
        self.assertIn("char tmp[MAX_PATH];", write)
        self.assertIn('lstrlenA(path) + sizeof(".tmp") > sizeof(tmp)', write)
        self.assertIn("lstrcpyA(tmp, path);", write)
        self.assertIn('lstrcatA(tmp, ".tmp");', write)
        self.assertIn(
            "CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,", write
        )
        self.assertEqual(write.count("WriteFile("), 2)
        self.assertIn("WriteFile(file, &magic, sizeof(magic), &wrote, NULL)", write)
        self.assertIn("wrote != sizeof(magic)", write)
        self.assertIn(
            "WriteFile(file, VV_MASK_TABLE, VV_MASK_TABLE_BYTES, &wrote, NULL)",
            write,
        )
        self.assertIn("wrote != VV_MASK_TABLE_BYTES", write)
        self.assertIn("FlushFileBuffers(file)", write)
        self.assertIn("if (!CloseHandle(file))", write)
        self.assertEqual(write.count("DeleteFileA(tmp);"), 2)
        self.assertNotIn("DeleteFileA(path);", write)
        writes_done = write.rindex("WriteFile(file, VV_MASK_TABLE")
        flush = write.index("FlushFileBuffers(file)")
        close = write.index("if (!CloseHandle(file))")
        publish = write.index("MoveFileExA(tmp, path,")
        self.assertLess(writes_done, flush)
        self.assertLess(flush, close)
        self.assertLess(close, publish)
        self.assertIn("MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH", write)

    def test_rebuilt_dll_imports_transactional_sidecar_apis(self) -> None:
        import pefile

        pe = pefile.PE(str(ROOT / self.manifest["companion_files"][0]["source"]))
        imports = {
            item.name.decode(errors="replace")
            for dll in pe.DIRECTORY_ENTRY_IMPORT
            for item in dll.imports
            if item.name is not None
        }
        self.assertTrue(
            {"WriteFile", "FlushFileBuffers", "CloseHandle", "MoveFileExA"}
            <= imports
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
