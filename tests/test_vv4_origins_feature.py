from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    _pe_checksum_layout,
    load_builds,
    load_patch_modes,
    load_fun_patches,
    render_patched_bytes,
)


STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
MANIFEST = ROOT / "data" / "vv4_origins_feature.json"
BUILDER = ROOT / "scripts" / "build_vv4_origins_feature.py"
COMPANION = ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"
FEATURE_ID = "vv4_enable_origins_exclusive_features"
RUNNING_PREFERENCE_ID = 38
MODES = (
    "collection_progression",
    "immediate_fixed",
)


class VV4OriginsFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock_bytes = STOCK.read_bytes()
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.build = next(item for item in load_builds() if item.id == "vv4")

    def test_exact_build_and_companion_identity(self) -> None:
        self.assertEqual(
            hashlib.sha256(self.stock_bytes).hexdigest().upper(),
            "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        )
        companion = self.manifest["companion_files"][0]
        self.assertEqual(
            companion["sha256"], hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper()
        )

    def test_all_guards_match_stock_and_payload_is_in_zero_cave(self) -> None:
        payload_patch = next(
            item
            for item in self.manifest["patches"]
            if int(item["offset"], 0) == 0x89373
        )
        payload = bytes.fromhex(payload_patch["after"])
        self.assertLessEqual(len(payload), 0xC8D)
        self.assertEqual(self.stock_bytes[0x89373 : 0x89373 + len(payload)], b"\0" * len(payload))
        for item in self.manifest["patches"]:
            offset = int(item["offset"], 0)
            before = bytes.fromhex(item["before"])
            after = bytes.fromhex(item["after"])
            self.assertEqual(self.stock_bytes[offset : offset + len(before)], before)
            self.assertEqual(len(before), len(after))
        section_patch = next(
            item for item in self.manifest["patches"] if int(item["offset"], 0) == 0x244
        )
        self.assertEqual(section_patch["before"], "40000040")
        self.assertEqual(section_patch["after"], "40000060")
        # The expanded-256 overlap check is gone with the data: those rows
        # only ever applied to modes that are not selectable, and the file
        # they lived in has been removed.

    def test_builder_uses_corrected_pe_and_details_guards(self) -> None:
        self.assertIn('patch(0x244, bytes.fromhex("40000040")', self.builder)
        self.assertIn('bytes.fromhex("891D5C904D00891D58904D00")', self.builder)
        self.assertIn('rel32_jump(0x447A25, detail_constructor) + b"\\x90" * 7', self.builder)
        self.assertIn("0x46AD80", self.builder)
        self.assertIn("VV4_MASTER_VALUE = 0x42C80000", self.builder)
        self.assertIn("call 0x46AF00", self.builder)
        # Village-wide rows are enabled via STATE_VILLAGE_WIDE/BUY only (0xA0000).
        # The old 0xA01C0 also set row-availability bits 6/7/8; bit 8 collided
        # with Time Warp's (row 0) "unavailable" bit (1 << (8 + row)) in the
        # companion DLL, making Time Warp show "Unavailable" whenever the
        # village-wide feature was installed. Pin the collision-free mask.
        self.assertIn("0xA0000", self.builder)
        self.assertNotIn("0xA01C0", self.builder)

    def test_vv4_native_upgrade_contract_is_emitted(self) -> None:
        record = json.loads(
            (ROOT / "data" / "vv4_origins_village_wide_upgrades.json").read_text(
                encoding="utf-8"
            )
        )
        fields = record["record_fields"]
        self.assertEqual(fields["native_skill_writer"], "0x46AD80")
        self.assertEqual(fields["native_skill_writer_index"], "skill ordinal 0..4")
        self.assertEqual(fields["mastery_target"], "Float32 100.0")
        self.assertEqual(
            fields["native_skill_writer_value"], "Float32 delta: 100.0-current"
        )
        changes = record["behavior_changes"]
        self.assertTrue(
            any("native Float32 skill writer" in change for change in changes),
            "village-wide Full Mastery behavior change is missing",
        )
        self.assertTrue(
            any("first free Like slot" in change for change in changes),
            "village-wide Running behavior change is missing",
        )

        ui = self.manifest["ui_contract"]
        self.assertEqual(ui["forbidden_helpers"], ["sub_40D8A0"])
        self.assertEqual(ui["native_factory"]["va"], "0x489F37")
        self.assertEqual(len(ui["result_helper"]["call_sites"]), 2)

        payload = bytes.fromhex(
            next(item for item in self.manifest["patches"] if item["offset"] == "0x89373")[
                "after"
            ]
        )
        self.assertIn(struct.pack("<I", 0x42C80000), payload)
        self.assertNotIn(struct.pack("<I", 0x42B40000), payload)

    def test_vv4_cure_and_running_source_guards_are_present(self) -> None:
        # Full Heal / Cure All restores every living villager below full
        # health to 100 -- not only villagers below an 80 partial-health
        # threshold -- so the heal gate must compare against 100, never 80.
        self.assertNotIn("cmp dword ptr [esi + 0x1C40], 80", self.builder)
        self.assertIn("lea eax, [esi + 0x1C34]", self.builder)
        self.assertIn("cmp dword ptr [esi + 0x1C40], 100", self.builder)
        self.assertIn("mov byte ptr [esi + 0x1C48], 0", self.builder)
        self.assertIn("inc dword ptr [0x4D6DF0]", self.builder)
        self.assertIn("je running_already", self.builder)
        # Grant Running (detail) grants through the game's managed like helpers
        # (add 0x45D2D0 / remove-dislike 0x45D1C0), not a raw array write, which
        # corrupts like state and crashes the game.
        self.assertNotIn("mov dword ptr [ecx], {RUNNING_PREFERENCE_ID}", self.builder)
        self.assertIn("call 0x45D2D0", self.builder)
        self.assertIn("call 0x45D1C0", self.builder)

    def test_time_warp_uses_the_vv1_to_vv4_proportional_clock_shift(self) -> None:
        """Regression test guarding against re-applying VV5's inverse-speed
        Time Warp formula to VV4.

        VV1 through VV4 share an offline catch-up that applies the injected
        elapsed-clock shift *divided* by the game-speed code, so a constant
        three-displayed-year advance requires a clock shift that scales
        directly *with* speed: ``speed * 3600`` seconds (10,800 / 21,600 /
        36,000 at speed 3 / 6 / 10). VV1's Origins research documents this as
        "its elapsed-clock adjustment scales with game speed", and VV2/VV3
        emit the same ``imul eax, eax, 3600``.

        VV5 alone multiplies elapsed time by speed and therefore needs the
        inverse ``129600 / speed`` (idiv). Copying VV5's idiv onto VV4 looks
        correct only at normal speed -- both give 21,600 -- but makes the paid
        warp advance ~12 years at half speed and ~1 year at double speed. This
        test pins VV4 to the proportional imul form.
        """
        try:
            import capstone
        except ImportError:
            self.skipTest("capstone not available")

        payload_patch = next(
            item for item in self.manifest["patches"] if int(item["offset"], 0) == 0x89373
        )
        payload = bytes.fromhex(payload_patch["after"])
        # Locate the 64-bit elapsed-clock write: sub dword ptr [0x4B8230], eax
        marker = bytes.fromhex("290530824B00")
        index = payload.find(marker)
        self.assertNotEqual(index, -1, "Time Warp clock write not found in payload")

        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        window_start = index - 0x18
        block = list(md.disasm(payload[window_start:index], 0x489373 + window_start))
        mnemonics = [insn.mnemonic for insn in block]

        self.assertIn(
            "imul",
            mnemonics,
            "VV4 Time Warp must scale the clock shift proportionally to speed",
        )
        self.assertNotIn(
            "idiv",
            mnemonics,
            "VV4 Time Warp must not use VV5's inverse 129600/speed clock shift",
        )
        imul = next(insn for insn in block if insn.mnemonic == "imul")
        self.assertEqual(
            int(imul.op_str.split(",")[-1].strip(), 0),
            3600,
            f"Time Warp scale factor is not 3600 seconds/speed-unit: {imul.op_str}",
        )

    def test_composes_with_current_vv4_features_in_all_modes(self) -> None:
        patch_ids = [patch.id for patch in load_fun_patches() if patch.game_id == "vv4"]
        self.assertIn(FEATURE_ID, patch_ids)
        self.assertIn("vv4_origins_village_wide_upgrades", patch_ids)
        self.assertNotIn("vv4_full_mastery_all_stage_a_candidate", patch_ids)
        self.assertNotIn("vv4_full_heal_cure_all_candidate", patch_ids)
        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(STOCK, self.build, mode, patch_ids)
                self.assertTrue(applied)
                checksum_offset, _ = _pe_checksum_layout(rendered)
                self.assertNotEqual(struct.unpack_from("<I", rendered, checksum_offset)[0], 0)
                self.assertNotEqual(bytes(rendered[0x89373 : 0x89373 + 4]), b"\0\0\0\0")

    def test_expanded_256_modes_are_removed(self) -> None:
        mode_ids = {mode.id for mode in load_patch_modes()}
        self.assertNotIn("experimental_expanded_256", mode_ids)
        self.assertNotIn("experimental_expanded_256_progression", mode_ids)

    def test_shr_section_is_executable_and_tail_jumps_target_it(self) -> None:
        """Regression test for two crash-causing bugs found by an
        independent PE re-parse of the real rendered output:

        1. VV4's .shr section -- where the base Origins feature writes its
           Cure helper, Island Event tech/food exclusions, and the
           village-wide preflight validator -- was never patched to be
           executable or to have its declared VirtualSize extended past 4
           bytes. Every other one of the five games explicitly does both
           for their own equivalent section. Confirmed unfixed anywhere in
           the repository before this fix landed.

        2. Two of the "bypass the Tech/Food Doubler for an Island Event
           tail-jump" patches computed their jump target as
           IMAGE_BASE + raw_file_offset instead of the correct .shr
           RVA-remapped VA -- landing in .data instead of the actual
           helper code.

        Both are verified here against the real rendered output, not the
        generator's own claims.
        """
        try:
            import pefile
            import capstone
        except ImportError:
            self.skipTest("pefile/capstone not available")

        for mode in MODES:
            with self.subTest(mode=mode):
                rendered, applied = render_patched_bytes(
                    STOCK, self.build, mode,
                    [FEATURE_ID, "vv4_origins_village_wide_upgrades"],
                )
                pe = pefile.PE(data=bytes(rendered), fast_load=True)
                shr = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".shr")
                self.assertTrue(
                    bool(shr.Characteristics & 0x20000000),
                    ".shr is still not marked executable",
                )
                self.assertGreaterEqual(
                    shr.Misc_VirtualSize, 0x1000,
                    ".shr VirtualSize was never extended to cover the injected code",
                )

                image_base = pe.OPTIONAL_HEADER.ImageBase
                shr_va_start = image_base + shr.VirtualAddress
                shr_va_end = shr_va_start + shr.SizeOfRawData
                md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
                md.detail = True
                checked_tail_jump = False
                for item in applied:
                    if item.get("purpose", "").startswith(
                        "bypass the Tech Doubler for an Island Event tail-jump"
                    ) or item.get("purpose", "").startswith(
                        "bypass the Food Doubler for an Island Event tail-jump"
                    ):
                        offset = int(item["offset"], 0)
                        after = bytes.fromhex(item["after"])
                        va = image_base + offset  # these live in .text, 1:1 mapped
                        insn = next(md.disasm(after, va))
                        self.assertEqual(insn.mnemonic, "jmp")
                        target = insn.operands[0].imm
                        self.assertTrue(
                            shr_va_start <= target < shr_va_end,
                            f"tail-jump at {item['offset']} targets {hex(target)}, "
                            f"outside .shr [{hex(shr_va_start)}, {hex(shr_va_end)})",
                        )
                        checked_tail_jump = True
                self.assertTrue(checked_tail_jump, "no tail-jump patches were found to check")


if __name__ == "__main__":
    unittest.main()
