from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"


def _load_builder():
    spec = importlib.util.spec_from_file_location("vv3_origins_slot_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load VV3 Origins builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VV3MaskSlotPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.builder = _load_builder()
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_exact_stock_save_builder_preimage_is_guarded(self) -> None:
        stock = STOCK.read_bytes()
        offset = self.builder.SAVE_SLOT_CAPTURE_FN - self.builder.IMAGE_BASE
        self.assertEqual(
            stock[offset : offset + self.builder.SAVE_SLOT_CAPTURE_LEN],
            self.builder.SAVE_SLOT_CAPTURE_BEFORE,
        )
        self.assertEqual(self.builder.SAVE_SLOT_CAPTURE_BEFORE.hex().upper(), "8B4424048B11")

    def test_manifest_contains_six_byte_save_slot_detour(self) -> None:
        patch = next(item for item in self.manifest["patches"] if item["offset"] == "0x3290")
        self.assertEqual(patch["before"], "8B4424048B11")
        self.assertEqual(len(bytes.fromhex(patch["after"])), 6)
        self.assertEqual(bytes.fromhex(patch["after"])[0], 0xE9)
        self.assertIn("capture save-builder", patch["purpose"])

    def test_capture_cave_is_in_appended_code_and_targets_data_slot(self) -> None:
        self.assertEqual(self.builder.SAVE_SLOT_CAPTURE_CAVE_VA, 0x6DF100)
        self.assertEqual(self.builder.SAVE_SLOT_PTR, 0x6E0044)
        self.assertEqual(self.builder.SAVE_SLOT_CAPTURE_RETURN_VA, 0x403296)
        cave = self.builder.assemble(
            f"""
                mov eax, dword ptr [esp + 4]
                mov dword ptr [0x{self.builder.SAVE_SLOT_PTR:X}], eax
                mov edx, dword ptr [ecx]
                jmp 0x{self.builder.SAVE_SLOT_CAPTURE_RETURN_VA:X}
            """,
            self.builder.SAVE_SLOT_CAPTURE_CAVE_VA,
        )
        self.assertEqual(cave[:4], bytes.fromhex("8B442404"))
        self.assertEqual(cave[4:9], bytes.fromhex("A344006E00"))
        self.assertEqual(cave[9:11], bytes.fromhex("8B11"))
        self.assertIn("0x6E0044", self.source.replace("0x006E0044", "0x6E0044"))
        section_patch = next(
            item
            for item in self.manifest["pe_append_transaction"]["layouts"][
                "collection_progression"
            ]["header_patches"]
            if item["offset"] == "0x2C8"
        )
        section_bytes = bytes.fromhex(section_patch["after"])
        self.assertIn(b".vv3mc", section_bytes)
        self.assertIn(b".vv3md", section_bytes)

    def test_slot_specific_path_and_fail_closed_slot_switch_are_source_guarded(self) -> None:
        self.assertIn('vvfp_masks_%d.dat', self.source)
        self.assertNotIn('vvfp_masks.dat', self.source)
        self.assertIn("return (slot >= 1 && slot <= 5) ? slot : 0;", self.source)
        self.assertIn("if (slot < 1 || slot > 5) return 0;", self.source)
        self.assertIn("if (g_vv3_mask_slot != slot)", self.source)
        self.assertIn("vv3_mask_clear_tables();", self.source)
        self.assertIn("g_vv3_mask_slot = slot;", self.source)
        self.assertIn("g_vv3_mask_loaded = 0;", self.source)
        self.assertIn("vv3_mask_read_sidecar(slot)", self.source)
        self.assertGreaterEqual(self.source.count("if (!vv3_mask_prepare_slot()) return 0;"), 2)

    def test_running_boundary_refreshes_only_matching_live_preimages(self) -> None:
        self.assertIn("#define VV3_RUNNING_BOUNDARY_PTR_SLOT 0x006E0048u", self.source)
        self.assertIn("g_vv3_running_before[VV3_MASK_SLOTS]", self.source)
        self.assertIn("g_vv3_running_capture = 0", self.source)
        boundary = self.source.split(
            "__declspec(dllexport) void __stdcall VV3RunningMaskBoundary", 1
        )[1].split("/* Render hook:", 1)[0]
        self.assertIn("if (!after)", boundary)
        self.assertIn("g_vv3_running_before[i] = vv3_mask_fingerprint(rec)", boundary)
        self.assertIn("g_vv3_running_mask_before[i]", boundary)
        self.assertIn("vv3_running_unique_stored_preimage_index(old_fp) != i", boundary)
        self.assertIn("vv3_running_unique_live_preimage_index(old_fp, slots)", boundary)
        self.assertIn("g_vv3_mask_fp[i] = vv3_mask_fingerprint(rec)", boundary)
        self.assertIn("rec[VV3_ACTIVE] != 0", boundary)
        self.assertIn("*(int *)(rec + VV3_HEALTH) > 0", boundary)
        self.assertIn("j = vv3_running_unique_live_preimage_index(old_fp, slots)", boundary)

    def test_collision_ambiguous_lookup_fails_before_same_slot_fast_path(self) -> None:
        """Neither a live nor stored duplicate may reach either return path."""
        live = self.source.split(
            "static int vv3_mask_unique_live_index(unsigned int fp) {", 1
        )[1].split("static int vv3_mask_unique_stored_index", 1)[0]
        self.assertIn("rec[VV3_ACTIVE] == 0", live)
        self.assertIn("*(const int *)(rec + VV3_HEALTH) <= 0", live)
        self.assertIn("if (found >= 0) return -1;", live)

        stored = self.source.split(
            "static int vv3_mask_unique_stored_index(unsigned int fp) {", 1
        )[1].split("/* ---- Sidecar persistence", 1)[0]
        self.assertIn("g_vv3_mask[i] == 0", stored)
        self.assertIn("g_vv3_mask_fp[i] != fp", stored)
        self.assertIn("if (found >= 0) return -1;", stored)

        getter = self.source.split(
            "__declspec(dllexport) int __stdcall VV3_GetMaskForRecord", 1
        )[1].split("/* Chooser commit:", 1)[0]
        live_gate = getter.index("vv3_mask_unique_live_index(fpv) != idx")
        stored_gate = getter.index("stored_idx = vv3_mask_unique_stored_index(fpv)")
        fast_path = getter.index("if (stored_idx == idx)")
        shifted_return = getter.index("return g_vv3_mask[stored_idx];")
        self.assertLess(live_gate, stored_gate)
        self.assertLess(stored_gate, fast_path)
        self.assertLess(fast_path, shifted_return)

    def test_nonzero_set_requires_unique_live_owner_and_rebinds_shifted_copy(self) -> None:
        """A stale setter pointer cannot seed a future fallback match."""
        setter = self.source.split(
            "__declspec(dllexport) int __stdcall VV3_SetMaskForRecord", 1
        )[1].split("/* ---- Mask draw", 1)[0]
        clamp = setter.index("if (mask < 0 || mask > VV3_MASK_MAX) mask = 0;")
        gate = setter.index("if (!vv3_mask_can_set_prepared(record, mask)) return 0;")
        owner = setter.index("live_idx = vv3_mask_unique_live_index(fpv);")
        rebind = setter.index("if (live_idx == idx)")
        write = setter.index("g_vv3_mask[idx] = (unsigned char)mask;")
        self.assertLess(clamp, gate)
        self.assertLess(gate, owner)
        self.assertLess(owner, rebind)
        self.assertLess(rebind, write)
        self.assertIn("i != idx", setter)
        self.assertIn("g_vv3_mask_fp[i] == fpv", setter)
        # The gate is nonzero-only: an explicit None may still clear an exact
        # stale slot even though it cannot claim a live fingerprint identity.
        can_set = self.source.split(
            "static int vv3_mask_can_set_prepared", 1
        )[1].split("/* ---- Sidecar persistence", 1)[0]
        self.assertIn("if (mask == 0) return 1;", can_set)
        self.assertIn("vv3_mask_unique_live_index", can_set)

    def test_individual_chooser_rejects_failed_mask_bind_before_staged_writes(self) -> None:
        chooser = self.source.split(
            "__declspec(dllexport) int __stdcall ShowVV3AppearanceChooser", 1
        )[1].split("/* ================= Change Appearance for All", 1)[0]
        bind = chooser.index("if (!VV3_SetMaskForRecord(record, vv3_appearance_mask))")
        head_write = chooser.index("*head = vv3_appearance_head;")
        body_write = chooser.index("*body = vv3_appearance_body;")
        self.assertLess(bind, head_write)
        self.assertLess(bind, body_write)
        self.assertIn("No tech points have been deducted.", chooser)

    def test_village_wide_mask_ambiguity_aborts_before_any_mutation_or_charge(self) -> None:
        engine = self.source.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        preflight = engine.index("if (mask_requested)")
        ambiguity = engine.index("!vv3_mask_can_set_prepared(r, probe)")
        head_body = engine.index("/* Head/Body: independent per-sex")
        first_record_write = engine.index("*(int *)(r + VV3_HEAD_OFF)")
        first_mask_write = engine.index("VV3_SetMaskForRecord")
        self.assertLess(preflight, ambiguity)
        self.assertLess(ambiguity, head_body)
        self.assertLess(ambiguity, first_record_write)
        self.assertLess(ambiguity, first_mask_write)
        self.assertIn("else if (mask_mode == 4) probe = 0;", engine)
        self.assertIn("else probe = 1;", engine)

        entry = self.source.split("ShowVV3AppearanceForAll(void)", 1)[1].split(
            "\n}", 1
        )[0]
        apply_at = entry.index("affected = vv3_apply_for_all")
        zero_guard = entry.index("if (affected == 0)", apply_at)
        ambiguity_message = entry.index(
            "The selected masks could not be safely matched", zero_guard
        )
        charge = entry.index("*tech -= VV3_CAF_COST", ambiguity_message)
        self.assertLess(apply_at, zero_guard)
        self.assertLess(zero_guard, ambiguity_message)
        self.assertLess(ambiguity_message, charge)

    def test_running_retag_uses_immutable_unique_live_and_stored_preimages(self) -> None:
        """Retagging must not cross two villagers that share the raw hash."""
        boundary = self.source.split(
            "__declspec(dllexport) void __stdcall VV3RunningMaskBoundary", 1
        )[1].split("/* Render hook:", 1)[0]
        snapshot = boundary.index("g_vv3_running_mask_before[i] =")
        capture = boundary.index("g_vv3_running_capture = 1;")
        stored_gate = boundary.index(
            "vv3_running_unique_stored_preimage_index(old_fp) != i"
        )
        live_gate = boundary.index(
            "vv3_running_unique_live_preimage_index(old_fp, slots)"
        )
        retag = boundary.index("g_vv3_mask_fp[i] = vv3_mask_fingerprint(rec)")
        self.assertLess(snapshot, capture)
        self.assertLess(capture, stored_gate)
        self.assertLess(stored_gate, live_gate)
        self.assertLess(live_gate, retag)
        self.assertIn(
            "g_vv3_running_mask_before[i] != fp",
            self.source.split(
                "static int vv3_running_unique_stored_preimage_index", 1
            )[1].split("/* Bracket every VV3 Grant Running", 1)[0],
        )

    def test_running_writers_are_bracketed_in_detail_and_village_wide_paths(self) -> None:
        builder = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(
            encoding="utf-8"
        )
        detail = builder.split("        detail_running:", 1)[1].split(
            "        detail_insufficient:", 1
        )[0]
        self.assertIn("RUNNING_BOUNDARY_BEFORE_CAVE_VA", detail)
        self.assertIn("RUNNING_BOUNDARY_AFTER_CAVE_VA", detail)
        self.assertLess(
            detail.index("RUNNING_BOUNDARY_BEFORE_CAVE_VA"),
            detail.index("mov dword ptr [ecx]"),
        )
        self.assertLess(
            detail.index("mov dword ptr [ecx]"),
            detail.index("RUNNING_BOUNDARY_AFTER_CAVE_VA"),
        )
        village = builder.split("        village_apply:", 1)[1].split(
            "        village_result:", 1
        )[0]
        # Keep the certified payload's original setup and one five-byte call;
        # the command-6-only boundary now lives in the appended .vv3mc wrapper.
        self.assertIn("RUNNING_VILLAGE_WRAPPER_CAVE_VA", village)
        wrapper = builder.split(
            "    running_village_wrapper_cave = assemble(", 1
        )[1].split("    # Save-slot capture", 1)[0]
        self.assertIn("cmp ebx, 6", wrapper)
        self.assertIn("RUNNING_BOUNDARY_BEFORE_CAVE_VA", wrapper)
        self.assertIn("RUNNING_BOUNDARY_AFTER_CAVE_VA", wrapper)
        self.assertIn("VILLAGE_WIDE_ENTRY_VA", wrapper)
        self.assertIn("put_cave(0x220, running_village_wrapper_cave", builder)

        full_dislike = builder.split("        running_full_removed:", 1)[1].split(
            "        running_already:", 1
        )[0]
        self.assertLess(
            full_dislike.index("RUNNING_BOUNDARY_BEFORE_CAVE_VA"),
            full_dislike.index("mov dword ptr [eax], -1"),
        )
        self.assertLess(
            full_dislike.index("mov dword ptr [eax], -1"),
            full_dislike.index("RUNNING_BOUNDARY_AFTER_CAVE_VA"),
        )

    def test_boundary_stubs_preserve_registers_and_have_disjoint_slots(self) -> None:
        builder = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(
            encoding="utf-8"
        )
        before = builder.split("running_boundary_before_cave = assemble(", 1)[1].split(
            "    running_boundary_after_cave = assemble(", 1
        )[0]
        after = builder.split("running_boundary_after_cave = assemble(", 1)[1].split(
            "    # Save-slot capture", 1
        )[0]
        for stub in (before, after):
            for instruction in (
                "push eax", "push ecx", "push edx",
                "pop edx", "pop ecx", "pop eax", "ret",
                "RUNNING_BOUNDARYFN_PTR",
            ):
                self.assertIn(instruction, stub)
        self.assertIn("put_cave(0x180, running_boundary_before_cave", builder)
        self.assertIn("put_cave(0x1C0, running_boundary_after_cave", builder)
        self.assertLess(0x180, 0x1C0)
        self.assertLess(0x1C0, 0x1000)

    def test_boundary_pointer_export_and_slot_count_contract_are_pinned(self) -> None:
        source = self.source
        self.assertIn(
            "*(void **)(UINT_PTR)VV3_RUNNING_BOUNDARY_PTR_SLOT = "
            "(void *)&VV3RunningMaskBoundary;",
            source,
        )
        exports = (ROOT / "native" / "vv3_full_mastery_candidate"
                   / "vv3_full_mastery_candidate.def").read_text(encoding="utf-8")
        self.assertIn("VV3RunningMaskBoundary=_VV3RunningMaskBoundary@4", exports)
        boundary = source.split(
            "__declspec(dllexport) void __stdcall VV3RunningMaskBoundary", 1
        )[1].split("/* Render hook:", 1)[0]
        self.assertIn("if (slots < 0) slots = 0;", boundary)
        self.assertIn("if (slots > VV3_MASK_SLOTS) slots = VV3_MASK_SLOTS;", boundary)
        clear = source.split("static void vv3_mask_clear_tables(void) {", 1)[1].split(
            "static int vv3_mask_captured_slot", 1
        )[0]
        self.assertIn("g_vv3_running_capture = 0;", clear)

    def test_sidecar_write_and_short_read_fail_closed(self) -> None:
        self.assertIn("WriteFile(h, g_vv3_mask, sizeof(g_vv3_mask)", self.source)
        self.assertIn("WriteFile(h, g_vv3_mask_fp, sizeof(g_vv3_mask_fp)", self.source)
        self.assertIn("mask_r != sizeof(g_vv3_mask)", self.source)
        self.assertIn("fp_r != sizeof(g_vv3_mask_fp)", self.source)
        self.assertIn("vv3_mask_clear_tables();", self.source)

    def test_loaded_sidecar_masks_are_range_sanitized_before_render(self) -> None:
        """A corrupt MSK3 byte must become no-mask before atlas indexing."""
        self.assertIn("static void vv3_mask_sanitize_loaded_table(void)", self.source)
        sanitizer = self.source.split(
            "static void vv3_mask_sanitize_loaded_table(void) {", 1
        )[1].split("static int vv3_mask_captured_slot", 1)[0]
        self.assertIn("if (g_vv3_mask[i] > VV3_MASK_MAX)", sanitizer)
        self.assertIn("g_vv3_mask[i] = 0;", sanitizer)
        self.assertIn("g_vv3_mask_fp[i] = 0;", sanitizer)

        reader = self.source.split(
            "static void vv3_mask_read_sidecar(int slot) {", 1
        )[1].split("static int vv3_mask_prepare_slot", 1)[0]
        self.assertIn("vv3_mask_sanitize_loaded_table();", reader)
        self.assertLess(
            reader.index("vv3_mask_sanitize_loaded_table();"),
            reader.index("CloseHandle(h);"),
        )

        # The two native atlas paths both derive their row from the returned
        # value; the getter must therefore retain its 0..5 contract.
        getter = self.source.split(
            "__declspec(dllexport) int __stdcall VV3_GetMaskForRecord", 1
        )[1].split("/* Chooser commit:", 1)[0]
        self.assertIn("return g_vv3_mask[idx];", getter)
        self.assertIn("return g_vv3_mask[stored_idx];", getter)
        self.assertIn("/* Render hook: mask (1..5)", self.source)


if __name__ == "__main__":
    unittest.main()
