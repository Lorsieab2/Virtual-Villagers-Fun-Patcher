from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
except ImportError:  # pragma: no cover - optional binary inspection dependencies
    pefile = None
    CS_ARCH_X86 = CS_MODE_32 = Cs = None


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
BUILDER = ROOT / "scripts" / "build_vv3_origins_feature.py"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"
DLL = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
HAVE_BINARY_DEPS = pefile is not None and Cs is not None


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

    def test_lookup_accepts_only_unique_owners_or_a_complete_uniform_group(self) -> None:
        """A collision group needs count parity and one shared stored value."""
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

        group = self.source.split(
            "static int vv3_mask_stored_group_value", 1
        )[1].split("static int vv3_mask_current_slot_writable", 1)[0]
        self.assertIn("live_count = vv3_mask_live_fingerprint_count(fp);", group)
        self.assertIn("if (live_count < 2) return 0;", group)
        self.assertIn("else if (value != g_vv3_mask[i])", group)
        self.assertIn("return stored_count == live_count ? value : 0;", group)

        getter = self.source.split(
            "__declspec(dllexport) int __stdcall VV3_GetMaskForRecord", 1
        )[1].split("/* Chooser commit:", 1)[0]
        active_gate = getter.index("rec[VV3_ACTIVE] == 0")
        live_gate = getter.index("live_idx = vv3_mask_unique_live_index(fpv)")
        group_gate = getter.index("group_value = vv3_mask_stored_group_value(fpv)")
        stored_gate = getter.index("stored_idx = vv3_mask_unique_stored_index(fpv)")
        fast_path = getter.index("if (stored_idx == idx)")
        shifted_return = getter.index("return g_vv3_mask[stored_idx];")
        self.assertLess(active_gate, live_gate)
        self.assertLess(live_gate, group_gate)
        self.assertLess(group_gate, stored_gate)
        self.assertLess(live_gate, stored_gate)
        self.assertLess(stored_gate, fast_path)
        self.assertLess(fast_path, shifted_return)

    def test_nonzero_set_requires_unique_live_owner_and_rebinds_shifted_copy(self) -> None:
        """A stale setter pointer cannot seed a future fallback match."""
        setter = self.source.split(
            "static int vv3_mask_apply_prepared", 1
        )[1].split("/* Chooser commit:", 1)[0]
        clamp = setter.index("if (mask < 0 || mask > VV3_MASK_MAX) mask = 0;")
        gate = setter.index("if (!vv3_mask_can_set_prepared(record, mask)) return 0;")
        owner = setter.index("live_idx = vv3_mask_unique_live_index(fpv);")
        rebind = setter.index("if (live_idx == idx")
        write = setter.index("shadow_mask[idx] = (unsigned char)mask;")
        persist = setter.index(
            "!vv3_mask_write_sidecar_tables(shadow_mask, shadow_fp)"
        )
        publish = setter.index("CopyMemory(g_vv3_mask, shadow_mask")
        self.assertLess(clamp, gate)
        self.assertLess(gate, owner)
        self.assertLess(owner, rebind)
        self.assertLess(rebind, write)
        self.assertLess(write, persist)
        self.assertLess(persist, publish)
        self.assertIn("i != idx", setter)
        self.assertIn("shadow_fp[i] == fpv", setter)
        # The exported individual path cannot target one member of a collision
        # group, including a None clear.  Only the full batch owns that path.
        can_set = self.source.split(
            "static int vv3_mask_can_set_prepared", 1
        )[1].split("/* ---- Sidecar persistence", 1)[0]
        self.assertIn("if (mask == 0)", can_set)
        self.assertIn("return !vv3_mask_has_duplicate_live_fingerprint(fpv);", can_set)
        self.assertIn("vv3_mask_unique_live_index", can_set)

        exported = self.source.split(
            "__declspec(dllexport) int __stdcall VV3_SetMaskForRecord", 1
        )[1].split("/* ---- Mask draw", 1)[0]
        self.assertIn("return vv3_mask_apply_prepared(record, mask, 1);", exported)

    def test_current_raw_slot_protects_foreign_unique_and_duplicate_live_owners(self) -> None:
        classifier = self.source.split(
            "static int vv3_mask_current_slot_writable", 1
        )[1].split("static int vv3_mask_current_slot_foreign_live", 1)[0]
        self.assertIn("if (g_vv3_mask[idx] == 0) return 1;", classifier)
        self.assertIn("if (current_fp == 0 || current_fp == target_fp) return 1;", classifier)
        self.assertIn("vv3_mask_unique_live_index(current_fp) >= 0", classifier)
        self.assertIn("vv3_mask_has_duplicate_live_fingerprint(current_fp)", classifier)

        foreign = self.source.split(
            "static int vv3_mask_current_slot_foreign_live", 1
        )[1].split("/* The caller must have prepared", 1)[0]
        self.assertIn("!vv3_mask_current_slot_writable(idx, target_fp)", foreign)
        self.assertIn("g_vv3_mask_fp[idx] != target_fp", foreign)

    def test_nonzero_foreign_conflict_and_none_preservation_are_pre_mutation(self) -> None:
        helper = self.source.split(
            "static int vv3_mask_apply_prepared", 1
        )[1].split("/* Chooser commit:", 1)[0]
        ownership = helper.index("current_foreign_live = vv3_mask_current_slot_foreign_live(idx, fpv);")
        conflict = helper.index("if (mask != 0 && current_foreign_live) return 0;")
        can_set = helper.index("if (!vv3_mask_can_set_prepared(record, mask)) return 0;")
        cleanup = helper.index("if (live_idx == idx)")
        preserve = helper.index("if (!(mask == 0 && current_foreign_live))")
        write = helper.index("shadow_mask[idx] = (unsigned char)mask;")
        persist = helper.index(
            "!vv3_mask_write_sidecar_tables(shadow_mask, shadow_fp)"
        )
        publish = helper.index("CopyMemory(g_vv3_mask, shadow_mask")
        self.assertLess(ownership, conflict)
        self.assertLess(conflict, can_set)
        self.assertLess(ownership, cleanup)
        self.assertLess(cleanup, preserve)
        self.assertLess(preserve, write)
        self.assertLess(write, persist)
        self.assertLess(persist, publish)
        self.assertIn("g_vv3_mask_last_persist_failed = 1;", helper)

        setter = self.source.split(
            "static int vv3_mask_can_set_prepared", 1
        )[1].split("/* ---- Sidecar persistence", 1)[0]
        self.assertIn("if (vv3_mask_unique_live_index(fpv) != idx) return 0;", setter)
        self.assertIn("return vv3_mask_current_slot_writable(idx, fpv);", setter)

    def test_batch_shadow_preserves_unselected_live_owners_and_clears_targets(self) -> None:
        shadow = self.source.split(
            "static int vv3_mask_build_batch_shadow", 1
        )[1].split("static int vv3_apply_for_all", 1)[0]
        self.assertIn("CopyMemory(out_mask, g_vv3_mask", shadow)
        self.assertIn("vv3_mask_plan_has_selected_fp", shadow)
        self.assertIn("out_mask[pos] = 0;", shadow)
        self.assertIn("vv3_mask_shadow_slot_available", shadow)
        self.assertIn("needed = vv3_mask_live_fingerprint_count(plan_fp[i]);", shadow)
        self.assertIn("out_mask[pos] = (unsigned char)desired[i];", shadow)
        self.assertIn("out_fp[pos] = plan_fp[i];", shadow)
        self.assertIn("if (placed != needed) return 0;", shadow)

    def test_all_ten_mask_options_feed_the_group_coherent_plan(self) -> None:
        engine = self.source.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        self.assertIn("if (mask_mode == 0)", engine)       # per-sex / Off
        self.assertIn("mask_mode == 1", engine)           # VV5-style
        self.assertIn("mask_mode == 2", engine)           # Random
        self.assertIn("mask_mode == 3", engine)           # Equal
        self.assertIn("mask_mode >= 4", engine)           # None + five fixed masks
        self.assertIn("vv3_mask_make_plan_group_coherent", engine)
        self.assertIn("vv3_mask_build_batch_shadow", engine)

        coherent = self.source.split(
            "static int vv3_mask_make_plan_group_coherent", 1
        )[1].split("static int vv3_mask_shadow_slot_available", 1)[0]
        self.assertIn("selected[j] != selected[i]", coherent)
        self.assertIn("desired[j] != canonical", coherent)
        self.assertIn("mask_mode >= 1 && mask_mode <= 3", coherent)
        self.assertIn("mask_mode == 1 && desired[j] == VV3_MASK_MAX", coherent)
        self.assertIn("desired[j] = canonical", coherent)
        self.assertIn("count != vv3_mask_live_fingerprint_count(plan_fp[i])", coherent)

    def test_batch_none_counts_any_stored_copy_and_shadow_clears_the_group(self) -> None:
        engine = self.source.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        compare = engine.split("/* Count each eligible record once", 1)[1].split(
            "if ((h >= 0", 1
        )[0]
        recovered = compare.index("int recovered_mask = VV3_GetMaskForRecord(r);")
        none = compare.index("if (desired_mask[i] == 0)", recovered)
        stored = compare.index("vv3_mask_has_stored_fingerprint(plan_fp[i])", none)
        self.assertLess(recovered, none)
        self.assertLess(none, stored)

        shadow = self.source.split(
            "static int vv3_mask_build_batch_shadow", 1
        )[1].split("static int vv3_apply_for_all", 1)[0]
        clear = shadow.index("vv3_mask_plan_has_selected_fp")
        allocate = shadow.index("if (seen || desired[i] == 0) continue;")
        self.assertLess(clear, allocate)

    def test_batch_preflight_finishes_before_count_or_mutation(self) -> None:
        engine = self.source.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        prepared = engine.index("if (!vv3_mask_prepare_slot())")
        plan = engine.index("Build the exact mask result before counting")
        coherent = engine.index("vv3_mask_make_plan_group_coherent")
        shadow = engine.index("vv3_mask_build_batch_shadow", coherent)
        count = engine.index("Count each eligible record once")
        head_body = engine.index("/* Head/Body: independent per-sex")
        first_record_write = engine.index("*(int *)(r + VV3_HEAD_OFF) = h")
        first_table_write = engine.index("CopyMemory(g_vv3_mask, shadow_mask")
        self.assertLess(prepared, plan)
        self.assertLess(plan, coherent)
        self.assertLess(coherent, shadow)
        self.assertLess(shadow, count)
        self.assertLess(count, head_body)
        self.assertLess(head_body, first_record_write)
        self.assertLess(shadow, first_table_write)

    def test_batch_publishes_the_proven_shadow_once_without_individual_setters(self) -> None:
        engine = self.source.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        persistence = engine.split("/* Durably publish the already-proven mask result", 1)[1].split(
            "/* Head/Body: independent per-sex", 1
        )[0]
        apply = engine.split("/* Publish the already-proven, already-persisted", 1)[1]
        self.assertNotIn("VV3_SetMaskForRecord(", engine)
        self.assertNotIn("vv3_mask_apply_prepared(", engine)
        self.assertIn(
            "!vv3_mask_write_sidecar_tables(shadow_mask, shadow_fp)", persistence
        )
        self.assertIn("g_vv3_caf_mask_persist_failed = 1;", persistence)
        self.assertIn("CopyMemory(g_vv3_mask, shadow_mask", apply)
        self.assertIn("CopyMemory(g_vv3_mask_fp, shadow_fp", apply)
        self.assertNotIn("vv3_mask_write_sidecar", apply)
        self.assertIn("if (mask_requested && mask_changed_any)", apply)

    def test_batch_sidecar_failure_precedes_every_appearance_mutation_and_charge(self) -> None:
        engine = self.source.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        persist = engine.index(
            "!vv3_mask_write_sidecar_tables(shadow_mask, shadow_fp)"
        )
        head_write = engine.index("*(int *)(r + VV3_HEAD_OFF) = h")
        table_write = engine.index("CopyMemory(g_vv3_mask, shadow_mask")
        self.assertLess(persist, head_write)
        self.assertLess(persist, table_write)
        ui = self.source.split(
            "__declspec(dllexport) int __stdcall ShowVV3AppearanceForAll", 1
        )[1]
        self.assertIn("g_vv3_caf_mask_persist_failed", ui)
        self.assertLess(ui.index("affected = vv3_apply_for_all"), ui.index("*tech -= VV3_CAF_COST;"))

    def test_record_index_is_bounded_by_the_current_population_slots(self) -> None:
        indexer = self.source.split("static int vv3_mask_index", 1)[1].split(
            "/* A raw preference fingerprint", 1
        )[0]
        self.assertIn("slots = *(int *)(UINT_PTR)VV3_SLOTS_PTR;", indexer)
        self.assertIn("if (slots < 0) return -1;", indexer)
        self.assertIn("if (slots > VV3_MASK_SLOTS) slots = VV3_MASK_SLOTS;", indexer)
        self.assertIn("if (idx >= (UINT_PTR)slots) return -1;", indexer)

    def test_individual_chooser_only_binds_changed_mask_before_staged_writes(self) -> None:
        chooser = self.source.split(
            "__declspec(dllexport) int __stdcall ShowVV3AppearanceChooser", 1
        )[1].split("/* ================= Change Appearance for All", 1)[0]
        changed_mask = chooser.index(
            "if (vv3_appearance_mask != orig_mask &&"
        )
        bind = chooser.index(
            "!VV3_SetMaskForRecord(record, vv3_appearance_mask)", changed_mask
        )
        head_write = chooser.index("*head = vv3_appearance_head;")
        body_write = chooser.index("*body = vv3_appearance_body;")
        self.assertLess(changed_mask, bind)
        self.assertLess(bind, head_write)
        self.assertLess(bind, body_write)
        self.assertIn("No tech points have been deducted.", chooser)

    @unittest.skipUnless(
        HAVE_BINARY_DEPS and DLL.is_file(),
        "requires pefile/capstone and the emitted VV3 candidate DLL",
    )
    def test_emitted_chooser_skips_unchanged_mask_setter_and_keeps_fail_gate(self) -> None:
        pe = pefile.PE(str(DLL))
        exports = {
            item.name.decode("ascii"): item.address
            for item in pe.DIRECTORY_ENTRY_EXPORT.symbols
            if item.name
        }
        chooser_va = pe.OPTIONAL_HEADER.ImageBase + exports["ShowVV3AppearanceChooser"]
        setter_va = pe.OPTIONAL_HEADER.ImageBase + exports["VV3_SetMaskForRecord"]
        chooser_raw = pe.get_offset_from_rva(exports["ShowVV3AppearanceChooser"])
        code = pe.__data__[chooser_raw : chooser_raw + 0x200]
        instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(code, chooser_va))

        # The compiler routes both the exported setter and the chooser through
        # the shared prepared helper.  Derive that private call target from the
        # stable exported wrapper instead of assuming the wrapper remains the
        # immediate call site.
        setter_raw = pe.get_offset_from_rva(exports["VV3_SetMaskForRecord"])
        setter_instructions = list(
            Cs(CS_ARCH_X86, CS_MODE_32).disasm(
                pe.__data__[setter_raw : setter_raw + 0x30],
                pe.OPTIONAL_HEADER.ImageBase + exports["VV3_SetMaskForRecord"],
            )
        )
        helper_va = next(
            int(instruction.op_str, 16)
            for instruction in setter_instructions
            if instruction.mnemonic == "call"
            and instruction.op_str.startswith("0x")
        )

        call_index = next(
            index
            for index, instruction in enumerate(instructions)
            if instruction.mnemonic == "call"
            and instruction.op_str == f"0x{helper_va:x}"
        )
        self.assertGreaterEqual(call_index, 3)
        # The changed-mask compare/branch is immediately before the setter
        # call.  Its taken edge skips the call and reaches the staged writes.
        self.assertEqual(instructions[call_index - 2].mnemonic, "push")
        self.assertEqual(instructions[call_index - 1].mnemonic, "push")
        # MSVC may use a short or near conditional branch; inspect the two
        # instructions before the argument setup rather than hardcoding RVAs.
        gate_index = next(
            index
            for index in range(call_index - 3, -1, -1)
            if instructions[index].mnemonic == "je"
        )
        self.assertIn("cmp", instructions[gate_index - 1].mnemonic)
        skip_target = int(instructions[gate_index].op_str, 16)
        self.assertGreater(skip_target, instructions[call_index].address)

        # A failed changed-mask bind tests EAX and branches to the failure
        # message; only a successful bind reaches the head/body writes.  The
        # shared helper has four stack arguments, so MSVC may clean them before
        # testing EAX.
        result_index = next(
            index
            for index in range(call_index + 1, len(instructions))
            if instructions[index].mnemonic == "test"
            and instructions[index].op_str == "eax, eax"
        )
        self.assertEqual(instructions[result_index + 1].mnemonic, "jne")
        write_addresses = {
            instruction.address
            for instruction in instructions[result_index + 1 :]
            if instruction.mnemonic == "mov"
            and instruction.op_str in ("dword ptr [edi], eax", "dword ptr [esi], eax")
        }
        self.assertTrue(write_addresses)
        self.assertLessEqual(skip_target, min(write_addresses))
        self.assertLess(instructions[result_index].address, min(write_addresses))

    def test_village_wide_mask_ambiguity_aborts_before_any_mutation_or_charge(self) -> None:
        engine = self.source.split("static int vv3_apply_for_all", 1)[1].split(
            "#define VW_RUNNING", 1
        )[0]
        preflight = engine.index("if (mask_requested)")
        plan = engine.index("Build the exact mask result before counting")
        group_gate = engine.index("!vv3_mask_make_plan_group_coherent", plan)
        shadow_gate = engine.index("!vv3_mask_build_batch_shadow", group_gate)
        ambiguity = engine.index(
            "g_vv3_caf_mask_fail = VV3_CAF_MASK_NO_ROOM;", shadow_gate
        )
        count = engine.index("Count each eligible record once")
        head_body = engine.index("/* Head/Body: independent per-sex")
        first_record_write = engine.index("*(int *)(r + VV3_HEAD_OFF) = h")
        first_mask_write = engine.index("CopyMemory(g_vv3_mask, shadow_mask")
        self.assertLess(preflight, plan)
        self.assertLess(plan, group_gate)
        self.assertLess(group_gate, shadow_gate)
        self.assertLess(shadow_gate, ambiguity)
        self.assertLess(ambiguity, count)
        self.assertLess(ambiguity, head_body)
        self.assertLess(ambiguity, first_record_write)
        self.assertLess(ambiguity, first_mask_write)

        entry = self.source.split("ShowVV3AppearanceForAll(void)", 1)[1].split(
            "\n}", 1
        )[0]
        apply_at = entry.index("affected = vv3_apply_for_all")
        zero_guard = entry.index("if (affected == 0)", apply_at)
        ambiguity_message = entry.index(
            "g_vv3_caf_mask_fail == VV3_CAF_MASK_AMBIGUOUS", zero_guard
        )
        charge = entry.index("*tech -= VV3_CAF_COST", ambiguity_message)
        self.assertLess(apply_at, zero_guard)
        self.assertLess(zero_guard, ambiguity_message)
        self.assertLess(ambiguity_message, charge)

        # Each refusal must name its own cause.  These four conditions used to
        # share one "could not be safely matched to unique villagers" message,
        # so a village that had simply never been saved reported a fingerprint
        # problem it did not have and the real cause was unactionable.
        causes = (
            "VV3_CAF_MASK_NO_SLOT",
            "VV3_CAF_MASK_BAD_MODE",
            "VV3_CAF_MASK_AMBIGUOUS",
            "VV3_CAF_MASK_NO_ROOM",
        )
        reported = entry[zero_guard:charge]
        for cause in causes:
            with self.subTest(cause=cause):
                self.assertIn(cause, reported)
        for opening in (
            "Masks cannot be changed until this village has been saved",
            "That mask option was not recognized",
            "Some villagers cannot be told apart",
            "There was no room to record the selected masks",
            "No eligible villagers matched the selected appearance options.",
        ):
            with self.subTest(message=opening):
                self.assertIn(opening, reported)
        # Every distinct cause is set exactly once in the engine, so no two
        # failures can collapse back onto a single reason.
        for cause in causes:
            with self.subTest(assignment=cause):
                self.assertEqual(
                    self.source.count(f"g_vv3_caf_mask_fail = {cause};"), 1
                )

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
        self.assertIn("WriteFile(h, mask_table, sizeof(g_vv3_mask)", self.source)
        self.assertIn("WriteFile(h, fp_table, sizeof(g_vv3_mask_fp)", self.source)
        self.assertIn("mask_r != sizeof(g_vv3_mask)", self.source)
        self.assertIn("fp_r != sizeof(g_vv3_mask_fp)", self.source)
        self.assertIn("vv3_mask_clear_tables();", self.source)

    def test_sidecar_write_is_transactional_with_checked_publication(self) -> None:
        write = self.source.split("static int vv3_mask_write_sidecar_tables", 1)[1].split(
            "static int vv3_mask_write_sidecar(void) {", 1
        )[0]
        self.assertIn("char tmp[MAX_PATH];", write)
        self.assertIn('lstrlenA(path) + (int)sizeof(".tmp") > MAX_PATH', write)
        self.assertIn("lstrcpyA(tmp, path);", write)
        self.assertIn('lstrcatA(tmp, ".tmp");', write)
        self.assertIn("CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,", write)
        self.assertEqual(write.count("WriteFile("), 3)
        for expected in (
            "WriteFile(h, &magic, sizeof(magic), &w, NULL)",
            "w != sizeof(magic)",
            "WriteFile(h, mask_table, sizeof(g_vv3_mask), &w, NULL)",
            "w != sizeof(g_vv3_mask)",
            "WriteFile(h, fp_table, sizeof(g_vv3_mask_fp), &w, NULL)",
            "w != sizeof(g_vv3_mask_fp)",
        ):
            self.assertIn(expected, write)
        self.assertIn("FlushFileBuffers(h)", write)
        self.assertIn("if (!CloseHandle(h))", write)
        self.assertEqual(write.count("DeleteFileA(tmp);"), 2)
        self.assertNotIn("DeleteFileA(path);", write)
        writes_done = write.rindex("WriteFile(h, fp_table,")
        flush = write.index("FlushFileBuffers(h)")
        close = write.index("if (!CloseHandle(h))")
        publish = write.index("MoveFileExA(tmp, path,")
        self.assertLess(writes_done, flush)
        self.assertLess(flush, close)
        self.assertLess(close, publish)
        self.assertIn("MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH", write)
        self.assertIn("return 0;", write)
        self.assertIn("return 1;", write)

    @unittest.skipUnless(HAVE_BINARY_DEPS, "pefile is unavailable")
    def test_rebuilt_dll_imports_transactional_sidecar_apis(self) -> None:
        pe = pefile.PE(str(DLL))
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
