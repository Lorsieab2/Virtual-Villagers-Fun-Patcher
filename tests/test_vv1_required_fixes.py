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

    def test_vv1_cure_all_restores_partial_health_and_clears_sickness(self) -> None:
        source = (ROOT / "scripts" / "build_vv1_origins_feature.py").read_text(
            encoding="utf-8"
        )
        cure = source.split("cure_all:", 1)[1].split("cure_done:", 1)[0]
        self.assertIn("cmp dword ptr [edx + 0x344], 80", cure)
        self.assertIn("mov dword ptr [edx + 0x344], 100", cure)
        self.assertIn("mov byte ptr [edx + 0x354], 0", cure)

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
