import hashlib
import re
import sys
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
STOCK = ROOT / "research" / "stock-executables"

from vv_fun_patcher import (  # noqa: E402
    get_fun_patch,
    identify,
    load_fun_patches,
    render_patched_bytes,
)


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
        self.assertIn("mov eax, 4", running)
        self.assertIn("lea ecx, [edx + 0x3A8]", running)

        # The Running eligibility/no-change scan itself lives in the
        # shared detail_preflight_code helper now (called by detail_menu
        # before it ever reaches its own charge path) -- also a 4-slot
        # scan, just with its own register usage.
        preflight = source.split("detail_preflight_code = assemble", 1)[1].split(
            "preflight_no_change:", 1
        )[0]
        self.assertIn("mov ecx, 4", preflight)

        mastery = source.split("detail_mastery:", 1)[1].split(
            "detail_success:", 1
        )[0]
        for offset in ("0x3BC", "0x3C0", "0x3C4", "0x3C8", "0x3CC"):
            self.assertIn(f"mov dword ptr [edx + {offset}], 100", mastery)
        self.assertNotIn("90", mastery)

    def test_vv1_cure_all_restores_full_health_and_clears_sickness(self) -> None:
        """Full Heal/Cure All Villagers: health is restored to 100 for
        anyone below 100 (not the old below-80 threshold), sickness is
        cleared, and the two counts are tracked in separate registers
        (eax = sick cured, ebp = healed) rather than one combined count,
        since the row must report and gate its charge on them
        separately.
        """
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        cure = source.split("cure_all:", 1)[1].split("cure_done:", 1)[0]
        self.assertNotIn("cmp dword ptr [edx + 0x344], 80", cure)
        self.assertIn("cmp dword ptr [edx + 0x344], 100", cure)
        self.assertIn("mov dword ptr [edx + 0x344], 100", cure)
        self.assertIn("inc ebp", cure)
        self.assertIn("mov byte ptr [edx + 0x354], 0", cure)
        self.assertIn("inc eax", cure)

        # The charge only happens once we already know something changed
        # (the "or ecx, ebp" / "jne cure_resolve" gate), and only after
        # the result DLL export actually resolves -- not unconditionally
        # like every other Tech-screen row.
        gate = cure.split("cure_check_result:", 1)[1]
        self.assertIn("or ecx, ebp", gate)
        self.assertIn("jne cure_resolve", gate)
        no_change = gate.split("cure_resolve:", 1)[0]
        self.assertIn("cure_no_change", no_change)
        self.assertNotIn("0xA2FC", no_change)
        resolve = gate.split("cure_resolve:", 1)[1]
        self.assertLess(
            resolve.index("sub dword ptr [edi + 0xA2FC], 30000"),
            resolve.index("call eax"),
            "charge must land before the result message is shown, only "
            "after the DLL export resolved",
        )

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
        # do_barrel shares the generic success path (which itself reaches
        # menu_done via the OFFICIAL-wording ROW_MESSAGE_HELPER call) rather
        # than displaying its own inline "Purchased." message and jumping
        # to menu_done directly.
        self.assertIn("jmp success", barrel)
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
        self.assertIn("jmp {full_like_target}", full_like)
        self.assertIn(
            '"always_clear_running_dislike": True',
            running.split('"vv1": {', 1)[1].split('"vv2": {', 1)[0],
        )

        # Confirm the rendered payload actually falls through into the
        # dislike-clearing scan (running_remove_dislikes, a few bytes
        # ahead) rather than skipping straight to running_next (tens of
        # bytes ahead) when a villager's Like slots are all full --
        # exactly the OFFICIAL spreadsheet's documented edge case: the
        # Running Dislike is still cleared for free even though the Like
        # itself can't be added.
        capstone = pytest.importorskip("capstone")
        source_exe = STOCK / "Virtual Villagers - A New Home.exe"
        if not source_exe.is_file():
            self.skipTest(f"stock executable not available: {source_exe}")
        build = identify(source_exe)
        rendered, _ = render_patched_bytes(
            source_exe, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features", "vv1_origins_village_wide_upgrades"],
        )
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        IMAGE_BASE = 0x400000
        SHR_FILE_OFFSET = 0x8B000
        SHR_RVA = 0x8D000
        running_va = IMAGE_BASE + SHR_RVA + 0x1F0  # code_va (0x1A0) + 0x50
        running_off = SHR_FILE_OFFSET + 0x1F0
        insns = list(md.disasm(rendered[running_off:running_off + 0xA0], running_va))
        mnemonics = [(i.mnemonic, i.op_str, i.address, i.size) for i in insns]
        full_like_index = next(
            idx for idx, (m, o, a, sz) in enumerate(mnemonics)
            if m == "inc" and o == "edi"
        )
        jump_mnemonic, jump_op, jump_addr, jump_size = mnemonics[full_like_index + 1]
        self.assertEqual(jump_mnemonic, "jmp")
        jump_target = int(jump_op, 16)
        self.assertLess(
            jump_target - (jump_addr + jump_size),
            0x10,
            "running_full_like must fall through into the nearby dislike scan, "
            "not skip past it to the far-away running_next",
        )

    def test_vv1_village_wide_granted_counts_are_scoped_and_wired(self) -> None:
        """New feature regression test: Grant Running and Grant Full
        Mastery both now report how many villagers were actually
        granted (not just how many were skipped), sourced from new
        scratch dwords the shared, cross-game
        scripts/build_village_wide_origins_features.py writes only when
        a game's own config opts in. report_mastery_counts stays
        VV1-only. report_running_granted is also VV1-only (VV3-VV5
        share the exact same code branches and must stay
        byte-identical) *except* for VV2, which opts in too --
        VV2's own ShowOriginsVillageWideResult call site
        (native/vv1_origins_icons/vv1_origins_icons.c, #included by
        VV2's own .c) shares VV1's exact 5-arg signature and always
        displays a "Granted Running to %d villagers." headline, so it
        needs a real value here, not a placeholder. Then disassembles
        the real rendered VV1 exe to confirm the wiring end to end: the
        village-wide caller reads the right scratch address for the
        right command, and the compiled DLL actually exports the entry
        points it resolves by name.
        """
        source = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(
            encoding="utf-8"
        )
        # Only VV1's (and, for report_running_granted, VV2's) config
        # *data* block may set either opt-in flag -- scoped to just the
        # CONFIG = {...} literal itself (bounded by "def assemble", the
        # first function after it), not the whole rest of the file,
        # which legitimately references these flag names many times in
        # the shared generator logic that reads them.
        config_literal = source.split("CONFIG = {", 1)[1].split("\ndef assemble", 1)[0]
        vv1_config, _, rest = config_literal.partition('\n    "vv2": {')
        vv2_config, _, other_configs = rest.partition('\n    "vv3": {')
        self.assertIn('"report_running_granted": True', vv1_config)
        self.assertIn('"report_mastery_counts": True', vv1_config)
        self.assertIn('"report_running_granted": True', vv2_config)
        self.assertNotIn("report_mastery_counts", vv2_config)
        self.assertNotIn("report_running_granted", other_configs)
        self.assertNotIn("report_mastery_counts", other_configs)

        capstone = pytest.importorskip("capstone")
        source_exe = STOCK / "Virtual Villagers - A New Home.exe"
        if not source_exe.is_file():
            self.skipTest(f"stock executable not available: {source_exe}")
        build = identify(source_exe)
        rendered, _ = render_patched_bytes(
            source_exe, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features", "vv1_origins_village_wide_upgrades"],
        )
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        IMAGE_BASE = 0x400000
        SHR_FILE_OFFSET = 0x8B000
        SHR_RVA = 0x8D000
        village_wide_entry_va = IMAGE_BASE + SHR_RVA + 0x1A0
        running_granted_va = village_wide_entry_va + 0x30
        mastery_granted_va = village_wide_entry_va + 0x38
        mastery_already_va = village_wide_entry_va + 0x3C

        village_wide_off = 0x8B549  # HEAL_CAVE village_wide: label, just past cure_all's own patch region start
        insns = list(md.disasm(rendered[village_wide_off:village_wide_off + 0xC0], IMAGE_BASE + SHR_RVA + (village_wide_off - SHR_FILE_OFFSET)))
        mnemonics_ops = [(i.mnemonic, i.op_str, i.address) for i in insns]

        cmp7 = next((a for m, o, a in mnemonics_ops if m == "cmp" and o == "ebx, 7"), None)
        self.assertIsNotNone(cmp7, "village_wide dispatch must branch on command 7 (Mastery)")

        running_reads = [o for m, o, a in mnemonics_ops if m == "mov" and f"0x{running_granted_va:x}" in o]
        self.assertTrue(running_reads, "Running path must read the granted count from its scratch dword")
        mastery_granted_reads = [o for m, o, a in mnemonics_ops if m == "mov" and f"0x{mastery_granted_va:x}" in o]
        mastery_already_reads = [o for m, o, a in mnemonics_ops if m == "mov" and f"0x{mastery_already_va:x}" in o]
        self.assertTrue(mastery_granted_reads, "Mastery path must read its granted count from its own scratch dword")
        self.assertTrue(mastery_already_reads, "Mastery path must read its already-mastered count from its own scratch dword")

        pefile = pytest.importorskip("pefile")
        dll_path = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"
        if not dll_path.is_file():
            self.skipTest(f"companion DLL not built: {dll_path}")
        pe = pefile.PE(str(dll_path))
        pe.parse_data_directories()
        exported = {
            symbol.name.decode(): symbol.address
            for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols
            if symbol.name
        }
        self.assertIn("ShowOriginsVillageWideResult", exported)
        self.assertIn("ShowOriginsMasteryResult", exported)

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

    def test_vv1_barrel_event_only_fires_after_tech_screen_closes(self) -> None:
        """Regression test for a real reported crash: buying Barrel of
        Babies used to fire the native event's own nested modal dialog the
        instant the token was set, while the Tech-screen Upgrades dialog
        (whose own "Buy" click just set that token) was still open and
        running its own modal loop. VV2's exact-build equivalent avoids
        this with a two-stage token advanced only from the Tech screen's
        own close branch; this checks VV1 now has the same second stage,
        by disassembling the real rendered exe rather than trusting the
        manifest's purpose strings.
        """
        capstone = pytest.importorskip("capstone")
        source = STOCK / "Virtual Villagers - A New Home.exe"
        if not source.is_file():
            self.skipTest(f"stock executable not available: {source}")
        build = identify(source)
        rendered, _ = render_patched_bytes(
            source, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features"],
        )

        IMAGE_BASE = 0x400000
        SHR_FILE_OFFSET = 0x8B000
        SHR_RVA = 0x8D000

        def to_va(file_offset: int) -> int:
            return IMAGE_BASE + SHR_RVA + (file_offset - SHR_FILE_OFFSET)

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

        # The original close branch at 0x435ACA must now redirect (jmp) into
        # the .shr cave rather than run the original two instructions
        # in place -- otherwise nothing was actually changed.
        close_branch = list(md.disasm(rendered[0x35AC2:0x35AD5], 0x435AC2))
        redirect = next(
            (i for i in close_branch if i.mnemonic == "jmp"), None
        )
        self.assertIsNotNone(
            redirect, "close branch no longer redirects into a helper"
        )
        helper_va = int(redirect.op_str, 16)
        helper_offset = helper_va - IMAGE_BASE - SHR_RVA + SHR_FILE_OFFSET

        # The helper must replay the exact original close sequence (sound,
        # stop-modal-loop call, screen-closed flag) -- this proves the fix
        # doesn't drop or alter any original behavior -- then advance the
        # token from 1 to 2, then return to the exact original shared exit
        # (0x435DCD). Compare mnemonic + operands rather than raw bytes:
        # the two CALLs below encode a position-relative rel32, which
        # necessarily differs now that the call site itself moved into the
        # .shr cave even though the absolute call targets are unchanged.
        # +70 rather than +60: the helper now also zeroes the Barrel delay
        # counter right before its final jmp, one more instruction than
        # before.
        helper_insns = list(md.disasm(rendered[helper_offset : helper_offset + 70], helper_va))
        actual = [(i.mnemonic, i.op_str) for i in helper_insns]
        expected_prefix = [
            ("mov", "ecx, dword ptr [esi + 0x14]"),
            ("push", "0x45"),
            ("call", "0x431470"),
            ("push", "0"),
            ("mov", "ecx, esi"),
            ("call", "0x40ae10"),
            ("mov", "eax, dword ptr [esi + 0xc]"),
            ("mov", "dword ptr [eax + 0xacb4], 1"),
        ]
        self.assertEqual(
            actual[: len(expected_prefix)],
            expected_prefix,
            "close helper does not replay the exact original close sequence",
        )
        tail = [(i.mnemonic, i.op_str) for i in helper_insns[len(expected_prefix) :]]
        self.assertIn(("cmp", "byte ptr [0x48d700], 1"), tail)
        self.assertIn(("mov", "byte ptr [0x48d700], 2"), tail)
        final_jmp = next(i for i in helper_insns if i.mnemonic == "jmp")
        self.assertEqual(int(final_jmp.op_str, 16), 0x435DCD)

        # The main-village-update owner must now require the fully-advanced
        # state (2), not merely "non-zero" -- so it never fires while the
        # Tech screen (which only ever sets state 1) is still open.
        main_helper_off = 0x8B710
        main_helper_va = to_va(main_helper_off)
        main_code = list(
            md.disasm(rendered[main_helper_off : main_helper_off + 0x12], main_helper_va)
        )
        cmp_insn = next(i for i in main_code if i.mnemonic == "cmp")
        self.assertEqual(cmp_insn.op_str, "byte ptr [0x48d700], 2")

    def test_vv1_barrel_event_waits_after_tech_screen_closes_before_firing(self) -> None:
        """New feature regression test: reported that the Barrel of
        Babies event popped up within a fraction of a second of closing
        the Tech screen, too fast to read the purchase confirmation
        first. Decompiling the main-village-update owner this helper is
        hooked into confirms it is a genuine per-frame tick (it rolls
        per-frame chances for ambient particle spawns), and Barrel of
        Babies is a hand-built event screen, not a natively-scheduled
        one like Island Event -- so the fix is a real elapsed-tick delay
        counter, not a scheduling-field write. Disassembles the real
        rendered exe to confirm the counter is incremented and compared
        against the real threshold before the event's own construct/
        run/teardown call sequence is ever reached, and that both the
        purchase-time and Tech-screen-close-time resets are wired.
        """
        capstone = pytest.importorskip("capstone")
        source = STOCK / "Virtual Villagers - A New Home.exe"
        if not source.is_file():
            self.skipTest(f"stock executable not available: {source}")
        build = identify(source)
        rendered, _ = render_patched_bytes(
            source, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features"],
        )
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        IMAGE_BASE = 0x400000
        SHR_FILE_OFFSET = 0x8B000
        SHR_RVA = 0x8D000

        def to_va(file_offset: int) -> int:
            return IMAGE_BASE + SHR_RVA + (file_offset - SHR_FILE_OFFSET)

        counter_va = to_va(0x8B704)

        # main-village-update helper: the counter must be incremented and
        # compared before the pushad/event-construction sequence, and the
        # comparison must be a real, nonzero threshold -- not accidentally
        # 0 or 1 (which would barely differ from firing immediately).
        main_helper_off = 0x8B710
        main_helper_va = to_va(main_helper_off)
        main_insns = list(
            md.disasm(rendered[main_helper_off:main_helper_off + 0x40], main_helper_va)
        )
        inc_insn = next(
            (i for i in main_insns if i.mnemonic == "inc" and f"0x{counter_va:x}" in i.op_str),
            None,
        )
        self.assertIsNotNone(inc_insn, "counter must be incremented on every tick the Tech screen is closed")
        cmp_insn = next(
            (i for i in main_insns if i.mnemonic == "cmp" and f"0x{counter_va:x}" in i.op_str),
            None,
        )
        self.assertIsNotNone(cmp_insn, "counter must be compared against a threshold")
        threshold = int(cmp_insn.op_str.rsplit(",", 1)[1].strip(), 0)
        self.assertGreater(threshold, 10, "threshold must be a real delay, not effectively immediate")
        jb_insn = main_insns[main_insns.index(cmp_insn) + 1]
        self.assertEqual(jb_insn.mnemonic, "jb", "must skip firing until the threshold is reached")
        pushad_index = next(i for i, insn in enumerate(main_insns) if insn.mnemonic == "pushal")
        self.assertLess(
            main_insns.index(inc_insn), pushad_index,
            "the counter check must happen before the event is constructed, not after",
        )

        # Purchase time (do_barrel) and Tech-screen-close time
        # (barrel_close_helper) must both reset the counter to 0, so a
        # second purchase after the first event fired doesn't inherit a
        # stale count and skip most of its own delay.
        source_text = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        do_barrel = source_text.split("do_barrel:", 1)[1].split("do_tech_doubler:", 1)[0]
        self.assertIn("mov dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}], 0", do_barrel)
        close_helper = source_text.split("barrel_close_helper_code = assemble", 1)[1].split(
            "BARREL_CLOSE_HELPER_VA,", 1
        )[0]
        self.assertIn("mov dword ptr [0x{BARREL_DELAY_COUNTER_VA:X}], 0", close_helper)

    def test_vv1_barrel_event_object_is_torn_down_with_its_matching_destructor(
        self,
    ) -> None:
        """Regression test for a real reported crash: buying Barrel of
        Babies, closing the Tech screen, and clicking OK on the resulting
        Island Event used to crash immediately, and left the save in a
        state that crashed again on the next launch. Decompiling the stock
        binary with IDA showed the helper constructed its temporary message
        object with sub_4286B0 (vtable off_459AE4) but tore it down with
        sub_42AB60 -- an unrelated method on a *different* class/vtable
        that itself calls sub_42A6A0 (the destructor for a different
        constructor, sub_42D0E0) under a flag check. That walks the wrong
        vtable and frees fields at the wrong offsets, corrupting the heap.
        The only destructor that matches sub_4286B0's own vtable is
        sub_427620. This disassembles the real rendered exe rather than
        trusting the manifest's purpose strings.
        """
        capstone = pytest.importorskip("capstone")
        source = STOCK / "Virtual Villagers - A New Home.exe"
        if not source.is_file():
            self.skipTest(f"stock executable not available: {source}")
        build = identify(source)
        rendered, _ = render_patched_bytes(
            source, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features"],
        )

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        main_helper_off = 0x8B710
        main_helper_va = 0x48D710
        insns = list(
            md.disasm(rendered[main_helper_off : main_helper_off + 0x60], main_helper_va)
        )
        calls = [i for i in insns if i.mnemonic == "call"]
        call_targets = [int(i.op_str, 16) for i in calls]

        self.assertIn(0x4286B0, call_targets, "constructor call is missing")
        self.assertIn(
            0x427620,
            call_targets,
            "helper must tear down the sub_4286B0 object with its own "
            "matching destructor (sub_427620), not an unrelated method",
        )
        self.assertNotIn(
            0x42AB60,
            call_targets,
            "0x42AB60 is not a destructor for this object's vtable and "
            "corrupts the heap when called on it",
        )

        # sub_427620 is a plain thiscall with no stack arguments (its own
        # disassembly ends in a bare `ret`, not `ret N`) -- the call site
        # must not push an argument for it first.
        dtor_call = next(i for i in calls if int(i.op_str, 16) == 0x427620)
        preceding = [i for i in insns if i.address < dtor_call.address]
        self.assertNotEqual(
            preceding[-1].mnemonic if preceding else None,
            "push",
            "sub_427620 takes no stack arguments; a stray push before "
            "the call would unbalance the stack",
        )

    def test_vv1_doublers_exclude_story_puzzle_and_milestone_rewards(self) -> None:
        """Regression test: the Tech/Food Point Doubler hooks intercept the
        game's single shared "add tech/food points" entry points, which
        every source of points -- scientist/farmer production, but also
        the Whale/berries/mushroom/device story puzzles and a one-time
        2-choice milestone dialog -- calls through. Only the native random
        Island Event caller was excluded from doubling; the puzzle and
        milestone callers were not, so completing the Whale puzzle (etc.)
        while a doubler was owned would double a one-time story reward,
        not production. Confirmed each caller's identity by resolving the
        actual VV1 string-table text at each site (e.g. "Your village has
        received a 1000-point food bonus!" for the Whale harvest outcome)
        before excluding it, rather than guessing from an address alone.
        This disassembles the real rendered exe and checks the actual
        comparison targets, not the manifest's purpose strings.
        """
        source = STOCK / "Virtual Villagers - A New Home.exe"
        if not source.is_file():
            self.skipTest(f"stock executable not available: {source}")
        build = identify(source)
        rendered, _ = render_patched_bytes(
            source, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features"],
        )

        # "cmp dword ptr [esp + 4], imm32" == 81 7C 24 04 <imm32 LE>. Every
        # doubler-exclusion check compiles to exactly this byte sequence, so
        # scan for it directly rather than guessing the caves' offsets.
        pattern = b"\x81\x7C\x24\x04"
        excluded = set()
        start = 0
        while True:
            index = rendered.find(pattern, start)
            if index == -1:
                break
            excluded.add(
                int.from_bytes(rendered[index + 4:index + 8], "little")
            )
            start = index + 1

        self.assertTrue(
            {0x428194, 0x41A378, 0x42BB18} <= excluded,
            "tech doubler must exclude the native Island Event return "
            "(0x428194), the story-puzzle dispatcher's tech award "
            "(0x41A378), and the milestone dialog's tech award (0x42BB18)",
        )
        self.assertTrue(
            {0x4281DA, 0x419459, 0x419F14, 0x42B86A} <= excluded,
            "food doubler must exclude the native Island Event return "
            "(0x4281DA), both story-puzzle dispatcher food awards "
            "(0x419459, 0x419F14), and the milestone dialog's food "
            "award (0x42B86A)",
        )

    def test_vv1_change_appearance_gates_charge_on_confirmed_result(self) -> None:
        """New feature regression test: the Villager Details "Change
        Appearance" row must never deduct tech points unless the icons
        DLL's picker actually returns success (the player clicked OK, not
        Cancel/closed the window, and the DLL/export resolved). Disassembles
        the real rendered exe -- both the detail_menu dispatch and the
        .shr helper it calls -- rather than trusting source text, and
        confirms the compiled DLL actually exports the entry point by
        name (not just that the source file says it should).
        """
        capstone = pytest.importorskip("capstone")
        source = STOCK / "Virtual Villagers - A New Home.exe"
        if not source.is_file():
            self.skipTest(f"stock executable not available: {source}")
        build = identify(source)
        rendered, _ = render_patched_bytes(
            source, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features"],
        )

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

        # detail_menu's dispatch must route row 4 (Change Appearance) to a
        # helper call before it ever reaches the generic table-driven
        # charge path used by rows 0-3 -- confirm the "cmp ebx, 4 / je"
        # appears, and resolve where it jumps to.
        # detail_menu grew a shared "permanent change" confirmation call
        # right after row selection (before this dispatch), so give the
        # window enough room for that plus the villager-lookup preamble
        # ahead of the row-4 check, not just the dispatch itself.
        detail_menu_off = 0x56E21
        dispatch = list(
            md.disasm(rendered[detail_menu_off:detail_menu_off + 0x80], 0x456E21)
        )
        cmp4 = next(
            (i for i in dispatch if i.mnemonic == "cmp" and i.op_str == "ebx, 4"),
            None,
        )
        self.assertIsNotNone(cmp4, "row 4 dispatch check is missing")
        jump = dispatch[dispatch.index(cmp4) + 1]
        self.assertEqual(jump.mnemonic, "je")
        router_va = int(jump.op_str, 16)

        # detail_menu's own dispatch must stay a bare two-instruction
        # "cmp ebx, 4 / je <router>" -- all of the call/test/branch logic
        # lives in a dedicated router in .shr, isolated from the shared,
        # byte-constrained detail_menu cave the other rows dispatch through.
        # .shr's raw file offset (0x8B000) differs from its mapped RVA
        # (0x8D000), so converting a VA there back to a file offset must
        # account for that remap rather than just subtracting IMAGE_BASE --
        # the router itself lives in .shr, not .text, so this correction
        # is needed even to reach the router's own bytes.
        IMAGE_BASE = 0x400000
        SHR_FILE_OFFSET = 0x8B000
        SHR_RVA = 0x8D000
        router_off = router_va - IMAGE_BASE - SHR_RVA + SHR_FILE_OFFSET

        # The router itself must call the helper and dispatch on its
        # three-way return value (1=changed, 2=OK-but-unchanged, anything
        # else=cancelled/insufficient funds, silent), rejoining the stable
        # detail_loop in every case.
        call_block = list(
            md.disasm(rendered[router_off:router_off + 0x18], router_va)
        )
        self.assertEqual(call_block[0].mnemonic, "call")
        appearance_helper_va = int(call_block[0].op_str, 16)
        self.assertEqual((call_block[1].mnemonic, call_block[1].op_str), ("cmp", "eax, 1"))
        self.assertEqual(call_block[2].mnemonic, "je")
        self.assertEqual((call_block[3].mnemonic, call_block[3].op_str), ("cmp", "eax, 2"))
        self.assertEqual(call_block[4].mnemonic, "je")

        # The .shr helper itself must check the tech-point balance (5000)
        # before ever resolving/calling the DLL, and must only deduct
        # after the resolved picker call's own return value is nonzero --
        # not unconditionally after merely showing the dialog.
        helper_off = appearance_helper_va - IMAGE_BASE - SHR_RVA + SHR_FILE_OFFSET
        helper_insns = list(
            md.disasm(rendered[helper_off:helper_off + 0x70], appearance_helper_va)
        )
        mnemonics = [(i.mnemonic, i.op_str) for i in helper_insns]
        self.assertEqual(mnemonics[0], ("cmp", "dword ptr [edi + 0xa2fc], 0x1388"))
        self.assertEqual(mnemonics[1][0], "jb")

        # LoadLibrary, GetProcAddress, the resolved picker call (through a
        # register -- its target isn't known until GetProcAddress
        # resolves it), and the native messagebox call on the
        # insufficient-funds path.
        calls = [i for i in helper_insns if i.mnemonic == "call"]
        register_calls = [i for i in calls if i.op_str == "eax"]
        self.assertEqual(
            len(register_calls), 1,
            "expected exactly one indirect call through a resolved export (the picker)",
        )
        picker_call = register_calls[0]

        # The picker returns 0 (cancelled), 1 (changed), or 2 (OK but
        # nothing changed) -- only 1 may reach the deduction below.
        after_picker = [i for i in helper_insns if i.address > picker_call.address]
        cmp_after_call = after_picker[0]
        self.assertEqual((cmp_after_call.mnemonic, cmp_after_call.op_str), ("cmp", "eax, 1"))
        jne_after_cmp = after_picker[1]
        self.assertEqual(jne_after_cmp.mnemonic, "jne")
        sub_insn = next(i for i in after_picker if i.mnemonic == "sub")
        self.assertEqual(sub_insn.op_str, "dword ptr [edi + 0xa2fc], 0x1388")
        # The deduction must come after the failure branch could have
        # already jumped away -- i.e. after the cmp+jne pair, not before.
        self.assertGreater(sub_insn.address, jne_after_cmp.address)

        # Finally, confirm the compiled companion DLL actually exports the
        # entry point this helper resolves by name -- not just that the C
        # source declares it.
        pefile = pytest.importorskip("pefile")
        dll_path = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"
        if not dll_path.is_file():
            self.skipTest(f"companion DLL not built: {dll_path}")
        pe = pefile.PE(str(dll_path))
        pe.parse_data_directories()
        exported = {
            symbol.name.decode(): symbol.address
            for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols
            if symbol.name
        }
        self.assertIn("ShowOriginsAppearancePicker", exported)

        # Disassemble the *compiled* export -- not the C source -- to confirm
        # the picker reads the real gender field. The current exact DLL uses
        # the equality result to populate its male flag and keeps the shared
        # 20-entry picker count; do not infer a 19-entry branch from an older
        # implementation.
        target_rva = exported["ShowOriginsAppearancePicker"]
        image_base = pe.OPTIONAL_HEADER.ImageBase
        va = image_base + target_rva
        image = pe.get_memory_mapped_image()
        # Keep this deliberately bounded, but large enough for the now-larger
        # compiled export after the mask persistence work.
        picker_insns = list(md.disasm(image[target_rva:target_rva + 0x200], va))
        # The compiler is free to either compare the gender field directly
        # from memory (cmp dword ptr [reg + 0x350], 1) or load it into a
        # register first and compare the register (mov reg, dword ptr
        # [reg + 0x350] ... cmp reg, 1) -- adding the "male" cache field to
        # appearance_state made the /O2 build switch from the former to the
        # latter, since the loaded value now also feeds the male flag store.
        # Either shape is a legitimate compiled branch on the real gender
        # field; only a fixed/absent comparison would be a bug.
        gender_load = next(
            (
                i for i in picker_insns
                if i.mnemonic == "mov" and i.op_str.endswith("+ 0x350]")
                and i.op_str.startswith("e")
            ),
            None,
        )
        gender_cmp = next(
            (
                i for i in picker_insns
                if i.mnemonic == "cmp" and (
                    re.fullmatch(r"dword ptr \[[a-z]{2,3} \+ 0x350\], 1", i.op_str)
                    or (
                        gender_load is not None
                        and i.op_str == f"{gender_load.op_str.split(',')[0]}, 1"
                    )
                )
            ),
            None,
        )
        self.assertIsNotNone(
            gender_cmp, "compiled picker must branch on the gender field (+0x350)"
        )
        after_cmp = picker_insns[picker_insns.index(gender_cmp) + 1:]
        gender_flag = next(
            (i for i in after_cmp if i.mnemonic in {"sete", "setne"}), None
        )
        self.assertIsNotNone(gender_flag, "must derive the male flag from the gender compare")
        self.assertEqual(gender_flag.mnemonic, "sete")
        self.assertEqual(gender_flag.op_str, "al")

    def test_vv1_every_upgrade_row_confirms_before_any_owned_check_or_charge(self) -> None:
        """New feature regression test: every purchasable row on both the
        Tech screen (menu, including its Village-Wide rows) and the
        Villager Details screen (detail_menu) must show the shared
        "permanent change" prompt before any tech points are spent.

        detail_menu confirms immediately after the row is picked, before
        its own eligibility logic (e.g. the Running preflight) runs.

        menu confirms at the top of its Buy path (charge:, gated only by
        the Time Warp pause no-op check) rather than immediately after
        the row is picked -- unlike detail_menu, a subset of menu's rows
        (the doublers) can be picked to *remove* something already owned,
        which is not a purchase and intentionally never reaches charge:
        or the confirmation at all (see remove_doubler in the source).
        What must hold for menu is: nothing that spends tech points (no
        write to the balance field, +0xA2FC) runs before the confirm
        call. Disassembles the real rendered exe for both dispatch sites
        and the shared .shr confirmation helper, and confirms the
        compiled DLL exports the entry point it resolves by name.
        """
        capstone = pytest.importorskip("capstone")
        source = STOCK / "Virtual Villagers - A New Home.exe"
        if not source.is_file():
            self.skipTest(f"stock executable not available: {source}")
        build = identify(source)
        rendered, _ = render_patched_bytes(
            source, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features"],
        )
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        IMAGE_BASE = 0x400000
        SHR_FILE_OFFSET = 0x8B000
        SHR_RVA = 0x8D000

        # detail_menu (Villager Details, including Change Appearance):
        # the confirm call must be the immediate next instruction after
        # the row is picked into ebx -- nothing else (no eligibility
        # check, no balance check, no charge) may run first.
        detail_off = 0x56E21
        detail_insns = list(md.disasm(rendered[detail_off:detail_off + 0x50], 0x456E21))
        detail_pick = next(
            i for i in detail_insns
            if i.mnemonic == "mov" and i.op_str == "ebx, eax"
        )
        detail_after_pick = detail_insns[detail_insns.index(detail_pick) + 1:]
        # The row (ebx) and the is_detail flag are pushed as args to the
        # shared confirm helper -- see confirm_helper_code -- immediately
        # followed by the call itself.
        self.assertEqual(detail_after_pick[0].mnemonic, "push")
        self.assertEqual(detail_after_pick[1].mnemonic, "push")
        self.assertEqual(detail_after_pick[2].mnemonic, "call")
        self.assertEqual(detail_after_pick[3].mnemonic, "test")
        self.assertEqual(detail_after_pick[4].mnemonic, "je")
        detail_confirm_va = int(detail_after_pick[2].op_str, 16)

        # menu (Tech screen, including Village-Wide): the row is picked
        # into ebx right after show_dialog returns, then the Buy path
        # (as opposed to remove_doubler) runs some read-only eligibility
        # checks (owned flags, population capacity) before reaching
        # charge:, where the confirm call sits right after the Time Warp
        # pause no-op check. Verify no balance-spending write happens
        # anywhere before that confirm call.
        menu_off = 0x569C0
        menu_va = 0x4569C0
        menu_insns = list(md.disasm(rendered[menu_off:menu_off + 0x120], menu_va))
        menu_pick = next(
            i for i in menu_insns
            if i.mnemonic == "mov" and i.op_str == "ebx, eax"
        )
        menu_confirm_call = next(
            i for i in menu_insns
            if menu_insns.index(i) > menu_insns.index(menu_pick)
            and i.mnemonic == "call"
            and int(i.op_str, 16) == detail_confirm_va
        )
        between = menu_insns[
            menu_insns.index(menu_pick) + 1 : menu_insns.index(menu_confirm_call)
        ]
        balance_writes = [
            i for i in between
            if i.mnemonic in ("sub", "add") and "0xa2fc" in i.op_str.lower()
        ]
        self.assertFalse(
            balance_writes,
            "menu must not spend any tech points before the confirm call",
        )
        menu_confirm_va = detail_confirm_va

        # The shared .shr helper itself: look the row's real cost up
        # (tech vs detail cost table, indexed by row), resolve the DLL,
        # resolve the export by name, call it with (row, cost), and
        # return its result untouched -- failing closed (returning 0/
        # Cancel) if either resolve step fails.
        confirm_off = menu_confirm_va - IMAGE_BASE - SHR_RVA + SHR_FILE_OFFSET
        helper_insns = list(md.disasm(rendered[confirm_off:confirm_off + 0x78], menu_confirm_va))
        mnemonics = [i.mnemonic for i in helper_insns]
        self.assertEqual(mnemonics[0], "mov", "must start by reading the row off the stack")
        cost_lookups = [
            i for i in helper_insns
            if i.mnemonic == "mov" and "ecx*4" in i.op_str
        ]
        self.assertGreaterEqual(
            len(cost_lookups), 2,
            "must look the row's cost up from both the tech and detail cost tables",
        )
        resolve_module = [
            i for i in helper_insns
            if i.mnemonic == "call" and "[0x457010]" in i.op_str
        ]
        resolve_export = [
            i for i in helper_insns
            if i.mnemonic == "call" and "[0x4570d4]" in i.op_str.lower()
        ]
        self.assertTrue(resolve_module, "must resolve the icons DLL module handle")
        self.assertTrue(resolve_export, "must resolve the confirm export by name")
        register_calls = [i for i in helper_insns if i.mnemonic == "call" and i.op_str == "eax"]
        self.assertEqual(len(register_calls), 1)
        fail_paths = [i for i in helper_insns if i.mnemonic == "xor" and i.op_str == "eax, eax"]
        self.assertTrue(fail_paths, "must fail closed (return 0) if the DLL/export can't be resolved")
        stack_cleanups = [i for i in helper_insns if i.mnemonic == "ret" and i.op_str == "8"]
        self.assertTrue(
            stack_cleanups, "must clean up both stack args (is_detail, row) with ret 8"
        )

        # Confirm the compiled DLL actually exports the entry point this
        # helper resolves by name, and that it really is an OK/Cancel +
        # question-icon prompt (VV5-task9 style: names the row and its
        # cost, not a fixed Yes/No notice) whose OK path returns nonzero.
        pefile = pytest.importorskip("pefile")
        dll_path = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"
        if not dll_path.is_file():
            self.skipTest(f"companion DLL not built: {dll_path}")
        pe = pefile.PE(str(dll_path))
        pe.parse_data_directories()
        exported = {
            symbol.name.decode(): symbol.address
            for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols
            if symbol.name
        }
        self.assertIn("ShowOriginsPermanentChangeConfirm", exported)
        target_rva = exported["ShowOriginsPermanentChangeConfirm"]
        image = pe.get_memory_mapped_image()
        confirm_insns = list(
            md.disasm(image[target_rva:target_rva + 0x100], pe.OPTIONAL_HEADER.ImageBase + target_rva)
        )
        pushes = [i.op_str for i in confirm_insns if i.mnemonic == "push"]
        # MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND
        # = 0x21 | 0x40000 | 0x10000 = 0x50021, IDOK = 1. (The compiler turns
        # "== IDOK" into a dec/neg/sbb/inc boolean idiom rather than a literal
        # cmp, so only the style flags are checked disassembly-side here.)
        # MB_TOPMOST/MB_SETFOREGROUND were added alongside the ported VV2
        # fullscreen fix (see vv1_surface_dialog/vv1_prep_fullscreen in
        # native/vv1_origins_icons/vv1_origins_icons.c) so this and every
        # other Origins message box stays above/foregrounded on the
        # fullscreen game window instead of painting behind it.
        self.assertIn("0x50021", pushes, "must be an OK/Cancel + question-icon, topmost+foreground prompt, not Yes/No")

    def test_vv1_time_warp_does_not_depend_on_the_game_speed(self) -> None:
        """Superseded the "reachable speed code" check: there is no code left.

        VV1's stock executable only ever assigns 3, 6 or 10 to the game-speed
        field, and the patch used to pick a different clock shift for each.
        That is what made the advance vary with the speed setting: measured on
        v1.34.23, NORMAL speed subtracted 21600 and advanced exactly three
        villager years, while HALF speed subtracted 10800 and advanced two.

        The branch now subtracts the measured three-year amount unconditionally,
        so it reads no speed field at all and there is no unreachable value to
        guard against.
        """
        capstone = pytest.importorskip("capstone")
        source = STOCK / "Virtual Villagers - A New Home.exe"
        if not source.is_file():
            self.skipTest(f"stock executable not available: {source}")
        build = identify(source)
        rendered, _ = render_patched_bytes(
            source, build, "collection_progression",
            ["vv1_enable_origins_exclusive_features"],
        )
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

        code = rendered[0x56900 : 0x56900 + 0x700]
        write = next(
            insn
            for insn in md.disasm(code, 0x456900)
            if insn.mnemonic == "sub" and "0x4860f0" in insn.op_str
        )
        # The whole instruction, immediate included: one constant, no register.
        self.assertEqual(write.op_str, "dword ptr [0x4860f0], 0x5460")
        self.assertEqual(0x5460, 21600)

        window = rendered[write.address - 0x400000 - 0x20 : write.address - 0x400000]
        block = list(md.disasm(window, write.address - 0x20))
        for insn in block:
            self.assertNotIn(
                insn.mnemonic, ("imul", "idiv", "cdq"),
                "VV1 Time Warp must not scale its clock shift",
            )
            # The speed FIELD itself must not be read. A bare `cmp reg, 3`
            # cannot be used as the signal here -- the surrounding menu code
            # compares the clicked row index against small integers too.
            self.assertNotIn(
                "0xa318", insn.op_str,
                f"VV1 Time Warp still reads the game-speed field: {insn.op_str}",
            )

if __name__ == "__main__":
    unittest.main()
