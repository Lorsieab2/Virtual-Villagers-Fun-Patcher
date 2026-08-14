import hashlib
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
        self.assertIn("mov ecx, 4", running)
        self.assertIn("mov eax, 4", running)
        self.assertIn("lea ecx, [edx + 0x3A8]", running)

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
        self.assertIn("jmp menu_done", barrel)
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
        self.assertIn("jmp running_next", full_like)

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
        helper_insns = list(md.disasm(rendered[helper_offset : helper_offset + 60], helper_va))
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
        detail_menu_off = 0x56E21
        dispatch = list(
            md.disasm(rendered[detail_menu_off:detail_menu_off + 0x60], 0x456E21)
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

        # The router itself must call the helper and only take the
        # success-message path when the helper's own return value is
        # nonzero, then rejoin the stable detail_loop in either case.
        call_block = list(
            md.disasm(rendered[router_off:router_off + 0x10], router_va)
        )
        self.assertEqual(call_block[0].mnemonic, "call")
        appearance_helper_va = int(call_block[0].op_str, 16)
        self.assertEqual(call_block[1].mnemonic, "test")
        self.assertEqual(call_block[2].mnemonic, "je")

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

        after_picker = [i for i in helper_insns if i.address > picker_call.address]
        test_after_call = after_picker[0]
        self.assertEqual((test_after_call.mnemonic, test_after_call.op_str), ("test", "eax, eax"))
        je_after_test = after_picker[1]
        self.assertEqual(je_after_test.mnemonic, "je")
        sub_insn = next(i for i in after_picker if i.mnemonic == "sub")
        self.assertEqual(sub_insn.op_str, "dword ptr [edi + 0xa2fc], 0x1388")
        # The deduction must come after the failure branch could have
        # already jumped away -- i.e. after the test+je pair, not before.
        self.assertGreater(sub_insn.address, je_after_test.address)

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

        # Male villagers only have 19 valid head/body values (0-18), not 20:
        # the villager-creation code assigns RNG(19) for male, RNG(20) for
        # everyone else (confirmed by decompiling the exact-build
        # initializer). Disassemble the *compiled* export -- not the C
        # source -- to confirm the count really is gender-dependent, since
        # this is exactly the class of bug (an assumed-uniform value that
        # is actually conditional) that caused the Barrel of Babies crash
        # this session.
        target_rva = exported["ShowOriginsAppearancePicker"]
        image_base = pe.OPTIONAL_HEADER.ImageBase
        va = image_base + target_rva
        image = pe.get_memory_mapped_image()
        picker_insns = list(md.disasm(image[target_rva:target_rva + 0x60], va))
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
                    i.op_str == "dword ptr [ecx + 0x350], 1"
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
        setne = next((i for i in after_cmp if i.mnemonic == "setne"), None)
        self.assertIsNotNone(setne, "must distinguish male (gender == 1) from everyone else")
        self.assertEqual(setne.op_str, "al")
        add19 = next(
            (i for i in after_cmp if i.mnemonic == "add" and i.op_str == "eax, 0x13"),
            None,
        )
        self.assertIsNotNone(
            add19, "must compute 19 (male) or 20 (everyone else), not a fixed 20"
        )

    def test_vv1_time_warp_double_speed_uses_a_reachable_game_speed_code(self) -> None:
        """Regression test: VV1's own stock executable only ever assigns
        3, 6, or 10 to the game-speed field Time Warp reads (verified with
        IDA against the real stock binary -- 6 distinct assignment sites,
        zero occurrences of 12 anywhere in the executable). The Origins
        Time Warp patch used to check for 12, a value the game can never
        actually produce, so double speed silently fell through to the
        6-hour "normal speed" adjustment instead of its own value.
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
        tail = next(
            insn
            for insn in md.disasm(code, 0x456900)
            if insn.mnemonic == "sub" and "0x4860f0" in insn.op_str
        )
        window = rendered[tail.address - 0x400000 - 0x20 : tail.address - 0x400000]
        block = list(md.disasm(window, tail.address - 0x20))

        double_speed_cmp = next(
            i for i in block if i.mnemonic == "cmp" and i.op_str.startswith("ecx, 0x")
            and int(i.op_str.split(", ")[1], 16) in (10, 12)
        )
        self.assertEqual(
            int(double_speed_cmp.op_str.split(", ")[1], 16),
            10,
            "double-speed check still uses a game-speed code VV1 never assigns",
        )
        double_speed_mov = block[block.index(double_speed_cmp) + 2]
        self.assertEqual(double_speed_mov.mnemonic, "mov")
        self.assertEqual(
            int(double_speed_mov.op_str.split(", ")[1], 16),
            36000,
            "double-speed adjustment is not the expected 10 hours",
        )


if __name__ == "__main__":
    unittest.main()
